import os
import time
import json
import secrets
from typing import Any, Dict, Optional, List, Callable

import httpx
from jose import jwt
from jose.exceptions import JWTError
from fastapi import Request, HTTPException
from starlette.responses import RedirectResponse, Response


def _env(name: str, default: Optional[str] = None) -> str:
    val = os.getenv(name, default)
    if val is None or val == "":
        raise RuntimeError(f"Missing required env var: {name}")
    return val


OIDC_ISSUER = _env("OIDC_ISSUER")  # e.g. http://auth.portal.local/realms/devops-lab
OIDC_CLIENT_ID = _env("OIDC_CLIENT_ID")  # e.g. portal
OIDC_CLIENT_SECRET = _env("OIDC_CLIENT_SECRET")
OIDC_REDIRECT_URI = _env("OIDC_REDIRECT_URI")  # e.g. http://portal.local/callback

SESSION_SECRET = _env("SESSION_SECRET")
SESSION_COOKIE = os.getenv("SESSION_COOKIE", "portal_session")
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "3600"))
REQUIRE_AUDIENCE = os.getenv("OIDC_REQUIRE_AUDIENCE", "true").lower() == "true"

# For local http on minikube:
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")  # lax is a good default for auth redirects


class OIDCConfig:
    def __init__(self, issuer: str):
        self.issuer = issuer.rstrip("/")
        self._loaded_at: float = 0.0
        self._cache: Dict[str, Any] = {}

    async def load(self) -> Dict[str, Any]:
        # Cache discovery document for 10 minutes
        now = time.time()
        if self._cache and (now - self._loaded_at) < 600:
            return self._cache

        url = f"{self.issuer}/.well-known/openid-configuration"
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            r.raise_for_status()
            self._cache = r.json()
            self._loaded_at = now
            return self._cache

    async def jwks(self) -> Dict[str, Any]:
        cfg = await self.load()
        jwks_uri = cfg["jwks_uri"]
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(jwks_uri)
            r.raise_for_status()
            return r.json()


_oidc = OIDCConfig(OIDC_ISSUER)


def _b64url_json(data: Dict[str, Any]) -> str:
    # Very small signed-cookie payload, not encrypted.
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def _sign(payload: str) -> str:
    # HMAC-ish via jose jwt (HS256) to avoid custom crypto:
    token = jwt.encode({"p": payload, "iat": int(time.time())}, SESSION_SECRET, algorithm="HS256")
    return token


def _unsign(token: str) -> str:
    data = jwt.decode(token, SESSION_SECRET, algorithms=["HS256"])
    return data["p"]


def make_login_redirect(state: str, nonce: str) -> RedirectResponse:
    # Build authorize URL from discovery document (loaded lazily elsewhere)
    # We'll compute it in handler where async is allowed.
    raise NotImplementedError


async def build_authorize_url(state: str, nonce: str) -> str:
    cfg = await _oidc.load()
    auth_endpoint = cfg["authorization_endpoint"]
    params = {
        "client_id": OIDC_CLIENT_ID,
        "response_type": "code",
        "scope": "openid profile email",
        "redirect_uri": OIDC_REDIRECT_URI,
        "state": state,
        "nonce": nonce,
    }
    # Simple query encoding:
    from urllib.parse import urlencode

    return f"{auth_endpoint}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str) -> Dict[str, Any]:
    cfg = await _oidc.load()
    token_endpoint = cfg["token_endpoint"]

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": OIDC_REDIRECT_URI,
        "client_id": OIDC_CLIENT_ID,
        "client_secret": OIDC_CLIENT_SECRET,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(token_endpoint, data=data)
        r.raise_for_status()
        return r.json()


async def verify_id_token(id_token: str) -> Dict[str, Any]:
    cfg = await _oidc.load()
    issuer = cfg["issuer"]

    jwks = await _oidc.jwks()
    # jose can select key by kid automatically if you pass jwks as key and set options
    options = {
        "verify_aud": REQUIRE_AUDIENCE,
        "verify_signature": True,
        "verify_exp": True,
        "verify_iss": True,
    }

    try:
        claims = jwt.decode(
            id_token,
            jwks,
            algorithms=["RS256"],
            issuer=issuer,
            audience=OIDC_CLIENT_ID if REQUIRE_AUDIENCE else None,
            options=options,
        )
        return claims
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid id_token: {e}")


def extract_roles(claims: Dict[str, Any]) -> List[str]:
    # Keycloak default: realm_access.roles
    roles = []
    ra = claims.get("realm_access") or {}
    rr = ra.get("roles") or []
    if isinstance(rr, list):
        roles.extend([str(x) for x in rr])

    # Also allow client roles if you decide to use them later:
    resource_access = claims.get("resource_access") or {}
    client = resource_access.get(OIDC_CLIENT_ID) or {}
    cr = client.get("roles") or []
    if isinstance(cr, list):
        roles.extend([str(x) for x in cr])

    # Dedup
    return sorted(set(roles))


def set_session(response: Response, user: Dict[str, Any]) -> None:
    # Store small user dict in signed cookie. Keep it small.
    now = int(time.time())
    payload = {
        "exp": now + SESSION_TTL_SECONDS,
        "sub": user.get("sub"),
        "preferred_username": user.get("preferred_username"),
        "email": user.get("email"),
        "name": user.get("name"),
        "roles": user.get("roles", []),
    }
    token = _sign(_b64url_json(payload))
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=SESSION_TTL_SECONDS,
        path="/",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def get_session_user(request: Request) -> Optional[Dict[str, Any]]:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    try:
        payload_str = _unsign(token)
        data = json.loads(payload_str)
        if int(data.get("exp", 0)) < int(time.time()):
            return None
        return data
    except Exception:
        return None


def require_user(request: Request) -> Dict[str, Any]:
    user = get_session_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_role(*required: str) -> Callable[[Request], Dict[str, Any]]:
    def _dep(request: Request) -> Dict[str, Any]:
        user = require_user(request)
        roles = set(user.get("roles") or [])
        if not roles.intersection(required):
            raise HTTPException(status_code=403, detail="Forbidden")
        return user

    return _dep


def new_state_nonce() -> Dict[str, str]:
    return {"state": secrets.token_urlsafe(24), "nonce": secrets.token_urlsafe(24)}
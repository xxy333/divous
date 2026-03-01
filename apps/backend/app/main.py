import os
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from starlette.middleware.cors import CORSMiddleware

from .auth import (
    new_state_nonce,
    build_authorize_url,
    exchange_code_for_tokens,
    verify_id_token,
    extract_roles,
    set_session,
    clear_session,
    get_session_user,
    require_user,
    require_role,
    _oidc,
)

app = FastAPI(title="DevOps Portal Lite")

# Optional, mostly for future API usage
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

APP_BASE_URL = os.getenv("APP_BASE_URL", "http://portal.local")
POST_LOGIN_REDIRECT = os.getenv("POST_LOGIN_REDIRECT", "/")

# Simple in-memory state/nonce store (MVP).
# NOTE: In real prod you'd store this server-side (redis) or encrypted cookie.
_state_nonce = {}


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.get("/readyz")
async def readyz():
    # Later: check DB connectivity etc.
    return {"ready": True}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user = get_session_user(request)
    if not user:
        return RedirectResponse(url="/login")

    roles = ", ".join(user.get("roles") or [])
    html = f"""
    <html>
      <head><title>DevOps Portal Lite</title></head>
      <body>
        <h1>DevOps Portal Lite</h1>
        <p>Logged in as: <b>{user.get("preferred_username")}</b></p>
        <p>Roles: <code>{roles}</code></p>

        <ul>
          <li><a href="/me">/me</a></li>
          <li><a href="/admin">/admin</a> (admin only)</li>
          <li><a href="/dev">/dev</a> (developer/admin)</li>
        </ul>

        <form method="post" action="/logout">
          <button type="submit">Logout</button>
        </form>
      </body>
    </html>
    """
    return HTMLResponse(html)


@app.get("/login")
async def login():
    sn = new_state_nonce()
    _state_nonce[sn["state"]] = sn["nonce"]
    authorize_url = await build_authorize_url(state=sn["state"], nonce=sn["nonce"])
    return RedirectResponse(url=authorize_url)


@app.get("/callback")
async def callback(code: str, state: str):
    nonce = _state_nonce.pop(state, None)
    if not nonce:
        return JSONResponse({"error": "invalid_state"}, status_code=400)

    tokens = await exchange_code_for_tokens(code)
    id_token = tokens.get("id_token")
    if not id_token:
        return JSONResponse({"error": "missing_id_token"}, status_code=400)

    claims = await verify_id_token(id_token)

    # (Optional) nonce validation - Keycloak includes nonce in id_token
    if claims.get("nonce") != nonce:
        return JSONResponse({"error": "invalid_nonce"}, status_code=400)

    user = {
        "sub": claims.get("sub"),
        "preferred_username": claims.get("preferred_username") or claims.get("preferred_username"),
        "email": claims.get("email"),
        "name": claims.get("name"),
        "roles": extract_roles(claims),
    }

    resp = RedirectResponse(url=POST_LOGIN_REDIRECT)
    set_session(resp, user)
    return resp


@app.post("/logout")
async def logout():
    resp = RedirectResponse(url="/")
    clear_session(resp)
    return resp


@app.get("/me")
async def me(user=Depends(require_user)):
    return user


@app.get("/admin")
async def admin(user=Depends(require_role("admin"))):
    return {"message": "Hello admin!", "user": user}


@app.get("/dev")
async def dev(user=Depends(require_role("developer", "admin"))):
    return {"message": "Hello developer!", "user": user}


# Warmup endpoint to validate discovery config quickly (optional)
@app.get("/oidc")
async def oidc_info():
    cfg = await _oidc.load()
    return {"issuer": cfg.get("issuer"), "authorization_endpoint": cfg.get("authorization_endpoint")}
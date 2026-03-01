# DevOps Portal Lite

**DevOps Portal Lite** je backend-only webová aplikace postavená na **FastAPI**, která demonstruje enterprise-grade autentizaci přes **OIDC (OAuth2 Authorization Code flow)** pomocí **Keycloak**, nasazení do **Kubernetes (minikube)** a základní produkční DevOps praktiky.

Projekt slouží jako **hands-on sandbox** pro rozvoj DevOps / Platform Engineering dovedností.

---

## ✨ Features

- OIDC autentizace přes **Keycloak**
- OAuth2 Authorization Code Flow (server-side, bez SPA)
- Server-side session (signed HTTP-only cookie)
- Role-based access control (RBAC)
  - `viewer`
  - `developer`
  - `admin`
- Backend-only FastAPI aplikace (HTML + JSON)
- Kubernetes deployment přes **Helm**
- NGINX Ingress routing
- Health & readiness probes
- Kubernetes Secrets & ConfigMaps
- Non-root container + resource limits

---

## 🧱 Architektura


Aplikace i Keycloak běží v jednom Kubernetes clusteru (minikube) a jsou vystaveny přes Ingress pomocí lokálních hostname.

---

## 🔐 Autentizační flow (OIDC)

1. Uživatel otevře `http://portal.local`
2. Backend přesměruje uživatele na Keycloak `/authorize`
3. Uživatel se autentizuje v Keycloaku
4. Keycloak přesměruje zpět na `/callback?code=...`
5. Backend:
   - vymění `code` za tokeny (`/token`)
   - ověří `id_token` (issuer, podpis, audience)
   - extrahuje role z tokenu
   - vytvoří server-side session (signed cookie)
6. Další requesty probíhají přes session cookie

👉 JWT tokeny se **neukládají do prohlížeče**.

---

## 🛠 Použitý stack

### Backend
- Python 3.11
- FastAPI
- Uvicorn
- httpx
- python-jose (JWT, JWKs)

### Identity & Auth
- Keycloak
- OAuth2 / OpenID Connect

### Infrastructure
- Docker
- Kubernetes (minikube)
- Helm
- NGINX Ingress Controller

---

## 📁 Struktura repozitáře


---

## ⚙️ Konfigurace (Environment Variables)

Backend je konfigurován pomocí environment variables:

| Proměnná | Popis |
|--------|------|
| `OIDC_ISSUER` | URL realm issuer (Keycloak) |
| `OIDC_CLIENT_ID` | Client ID |
| `OIDC_CLIENT_SECRET` | Client secret |
| `OIDC_REDIRECT_URI` | Callback URL |
| `SESSION_SECRET` | Secret pro podepisování session |
| `COOKIE_SECURE` | Secure flag pro cookie |
| `COOKIE_SAMESITE` | SameSite policy |

---

## 🚀 Lokální běh (minikube)

### 1) Povolení ingress controlleru
```bash
minikube addons enable ingress

2) Build Docker image do minikube
eval $(minikube docker-env)
docker build -t devops-portal-backend:local apps/backend

3) Deploy aplikace přes Helm

helm upgrade --install devops-portal deploy/helm/devops-portal \
  --set image.repository=devops-portal-backend \
  --set image.tag=local

4) Nastavení /etc/hosts

<MINIKUBE_IP> portal.local auth.portal.local

5) Ověření
curl http://portal.local/healthz

```
| Endpoint    | Popis              | Role             |
| ----------- | ------------------ | ---------------- |
| `/`         | Hlavní stránka     | authenticated    |
| `/login`    | OIDC login         | public           |
| `/callback` | OIDC callback      | public           |
| `/logout`   | Logout             | authenticated    |
| `/me`       | Info o uživateli   | authenticated    |
| `/dev`      | Developer endpoint | developer, admin |
| `/admin`    | Admin endpoint     | admin            |
| `/healthz`  | Liveness probe     | public           |
| `/readyz`   | Readiness probe    | public           |

---


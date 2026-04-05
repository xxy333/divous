# Changelog

Všechny změny v projektu jsou zdokumentovány v tomto souboru.

Formát vychází z [Keep a Changelog](https://keepachangelog.com/cs/1.0.0/).

---

## [Unreleased]

### Added
- React (TypeScript + Vite) frontend aplikace v `apps/frontend/`
- Helm šablona `frontend.yaml` pro nasazení frontendu do Kubernetes
- Aktualizovaný Ingress routing – backend API paths vs. frontend

---

## [0.3.0] – 2026-04-05

### Keycloak auto-setup sidecar + glassmorphic frontend

#### Added
- **Keycloak sidecar kontejner** (`keycloak.yaml`): nový kontejner `keycloak-setup` (Alpine) se automaticky spustí po startu Keycloaku a přes REST API nakonfiguruje celý realm – klienta, role a uživatele. Realm se obnoví při každém restartu podu bez manuálního zásahu.
- **ConfigMap `keycloak-setup-script`**: setup skript uložen v Kubernetes ConfigMap, snadno editovatelný bez rebuildu image.
- **Keycloak přidán do Helm chartu** (`keycloak.yaml`): Deployment, Service i ConfigMap jsou nyní spravovány Helmem (Revision 14). Keycloak byl dříve nasazen manuálně přes přímý manifest.
- **Glassmorphic UI design** (`index.css`, `Navbar.module.css`, `Page.module.css`): kompletní redesign frontendu – frosted glass karty s `backdrop-filter: blur()`, animované barevné orby na pozadí (`floatOrb` keyframe), shimmer gradient text na nadpisech a navbaru.
- **3D tilt efekt na kartách** (`TiltCard.tsx`, `TiltCard.module.css`): nová reusable komponenta sledující pozici myši a aplikující `perspective + rotateX + rotateY` transformaci s radial gradientem pod kurzorem.
- **Typing efekt** (`HomePage.tsx`): uvítací text se postupně „píše" pomocí vlastního `useTyping` hooku s blikajícím kurzorem.
- **Animovaný loading spinner** (`App.tsx`): rotující CSS spinner místo statického textu při načítání.

#### Fixed
- **Karty Developer/Admin nepracovaly jako navigační odkazy**: React routy `/dev` a `/admin` kolidovaly s backend API cestami v Ingressu. Přejmenováno na `/dashboard/dev` a `/dashboard/admin`.
- **Keycloak klient – `postLogoutRedirectUris`**: pole neexistuje v Keycloak 26 `ClientRepresentation`; nahrazeno správným `attributes[\"post.logout.redirect.uris\"]`.
- **Alpine image bez curl**: sidecar příkaz upraven na `apk add --no-cache curl && sh /scripts/setup.sh`.

#### Changed
- Navbar a card hover efekty přesunuty z CSS do JS (`TiltCard`) pro plynulejší 3D animaci.
- Statické karty (Uživatel, Role) nyní reagují na hover – glass highlight, scale a rotace ikony.

---

## [0.2.0] – 2026-04-04

### Nasazení na minikube – opravy a konfigurace

#### Added
- `DEPLOY.md` – kompletní průvodce nasazením na minikube (DNS, Keycloak, Helm, tunnel)
- `keycloakHostAlias` v Helm `values.yaml` + `backend.yaml` – `hostAliases` v backend podu umožňují přeložit `auth.portal.test` na ClusterIP Keycloak service uvnitř clusteru
- Keycloak nasazen přes přímý Kubernetes manifest s oficiálním image `quay.io/keycloak/keycloak:26.1`
- Keycloak `KC_HOSTNAME=auth.portal.test` a `KC_HOSTNAME_STRICT=false` pro správné generování veřejných URL v discovery dokumentu
- Realm `devops-lab`, klient `portal`, role `viewer`/`developer`/`admin` a testovací uživatelé `alice`/`bob`/`carol` konfigurováni přes Keycloak REST API
- `post_logout_redirect_uri` přidán do Keycloak klienta `portal`

#### Fixed
- **`at_hash` JWT validace** (`auth.py`, `main.py`): `verify_id_token()` nově přijímá `access_token` parametr a předává ho do `jwt.decode()` pro správné ověření `at_hash` claimu v ID tokenu
- **Logout HTTP 405** (`main.py`): `RedirectResponse` po logout změněn ze status 307 na **303 See Other** – prohlížeč po odhlášení provede GET místo POST
- **Logout neukončoval Keycloak SSO session** (`main.py`): Logout endpoint nově přesměrovává na Keycloak `end_session_endpoint` s `post_logout_redirect_uri`, čímž ukončuje SSO session a zabraňuje automatickému přihlášení
- **`OIDC_CLIENT_ID` NameError** (`main.py`): Přidán import `OIDC_CLIENT_ID` z `auth` modulu (byl chybějící po přidání logout flow)
- **`OIDC_ISSUER` interní URL** (`values.yaml`): Změněno z `http://auth.portal.local/realms/devops-lab` na `http://auth.portal.test/realms/devops-lab` (veřejná URL) – backend se nyní ptá Keycloaku pod veřejným hostname, čímž dostává správné `authorization_endpoint` URL pro přesměrování prohlížeče

#### Changed
- `values.yaml`: `portalHost`, `apiHost` → `portal.test`; `keycloakHost` → `auth.portal.test`
- `values.yaml`: `env.oidcIssuer` aktualizován na veřejnou URL `http://auth.portal.test/realms/devops-lab`

---

## [0.1.0] – initial commit

### Added
- FastAPI backend (`apps/backend/`) s OIDC autentizací přes Keycloak
  - Authorization Code Flow (server-side, bez SPA)
  - Server-side session podepsaná HMAC cookie
  - RBAC middleware (`require_role()`) pro role `viewer`, `developer`, `admin`
  - Endpointy: `/`, `/login`, `/callback`, `/logout`, `/me`, `/dev`, `/admin`, `/healthz`, `/readyz`, `/oidc`
  - Health & readiness probes
  - Non-root container (UID 1001), resource limits
- Dockerfile pro backend (`python:3.11-slim`, non-root user)
- Helm chart `deploy/helm/devops-portal/`
  - `backend.yaml` – Deployment + Service
  - `secrets.yaml` – Kubernetes Secret pro `OIDC_CLIENT_SECRET` a `SESSION_SECRET`
  - `ingress.yaml` – NGINX Ingress pro `portal.test` a `auth.portal.test`
  - `frontend.yaml`, `keycloak.yaml`, `postgres.yaml` – připravené šablony (zatím prázdné)
  - `values.yaml` – konfigurace prostředí
- `README.md` – přehled projektu, architektura, stack, konfigurace, API endpointy

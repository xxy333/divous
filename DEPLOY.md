# DevOps Portal – Průvodce nasazením na minikube

Tento dokument popisuje **kompletní postup** nasazení aplikace DevOps Portal Lite na lokální Kubernetes cluster (minikube) na macOS. Zahrnuje všechny kroky včetně konfigurace Keycloaku, DNS a sítě.

---

## Obsah

1. [Prerekvizity](#1-prerekvizity)
2. [Spuštění minikube](#2-spuštění-minikube)
3. [Build Docker image backendu](#3-build-docker-image-backendu)
4. [Nasazení Keycloaku](#4-nasazení-keycloaku)
5. [Konfigurace Keycloaku přes REST API](#5-konfigurace-keycloaku-přes-rest-api)
6. [Nasazení backendu přes Helm](#6-nasazení-backendu-přes-helm)
7. [DNS konfigurace na macOS](#7-dns-konfigurace-na-macos)
8. [Zpřístupnění aplikace přes minikube tunnel](#8-zpřístupnění-aplikace-přes-minikube-tunnel)
9. [Ověření funkčnosti](#9-ověření-funkčnosti)
10. [Testovací účty](#10-testovací-účty)
11. [Přehled endpointů](#11-přehled-endpointů)
12. [Opravy a known issues](#12-opravy-a-known-issues)
13. [Časté problémy](#13-časté-problémy)

---

## 1. Prerekvizity

Ujisti se, že máš nainstalované následující nástroje:

| Nástroj | Účel |
|---------|------|
| [minikube](https://minikube.sigs.k8s.io/) | Lokální Kubernetes cluster |
| [kubectl](https://kubernetes.io/docs/tasks/tools/) | Komunikace s clusterem |
| [helm](https://helm.sh/) | Nasazení aplikace přes Helm charty |
| [docker](https://www.docker.com/) | Build Docker image backendu |
| [brew](https://brew.sh/) | Instalace dnsmasq na macOS |

---

## 2. Spuštění minikube

```bash
minikube start
```

Minikube automaticky nastaví `kubectl` kontext na nový cluster. Na macOS s Docker driverem (výchozí) běží cluster uvnitř Docker kontejneru – **node IP není přímo dostupná z macOS hostu** (viz sekce 8).

Ověření, že ingress addon je povolen (potřebný pro routování HTTP):

```bash
minikube addons enable ingress
```

> Pokud byl minikube spuštěn dříve a ingress byl již povolen, příkaz to oznámí – to je v pořádku.

---

## 3. Build Docker image backendu

Backend musíme buildnout přímo **do minikube Docker daemonu** – jinak ho Kubernetes nenajde (nekopíruje image z lokálního Docker daemonu hostu do clusteru).

```bash
# Zjistíme proměnné prostředí minikube Docker daemonu
minikube docker-env --shell bash
# Výstup vypadá takto:
# export DOCKER_TLS_VERIFY="1"
# export DOCKER_HOST="tcp://127.0.0.1:XXXXX"
# export DOCKER_CERT_PATH="/Users/.../.minikube/certs"

# Build image s těmito proměnnými (nahraď hodnoty z výstupu výše)
DOCKER_TLS_VERIFY=1 \
DOCKER_HOST=tcp://127.0.0.1:<PORT> \
DOCKER_CERT_PATH=/Users/<USER>/.minikube/certs \
docker build -t devops-portal-backend:local apps/backend
```

> **Proč `imagePullPolicy: Never`?** Říkáme Kubernetes, aby image nehledal ve vzdáleném registry, ale použil lokálně buildnutý. To nastavujeme v Helm hodnotách.

---

## 4. Nasazení Keycloaku

### Proč ne Bitnami Helm chart?

Bitnami od srpna 2025 omezil přístup ke svým image – pull failuje s `ErrImagePull` bez předplatného. Proto používáme **oficiální Keycloak image** z `quay.io`.

### Nasazení přes manifest

```bash
kubectl apply -f - <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: keycloak
  labels:
    app: keycloak
spec:
  replicas: 1
  selector:
    matchLabels:
      app: keycloak
  template:
    metadata:
      labels:
        app: keycloak
    spec:
      containers:
        - name: keycloak
          image: quay.io/keycloak/keycloak:26.1
          args: ["start-dev"]
          env:
            - name: KC_HOSTNAME_STRICT
              value: "false"
            - name: KC_HTTP_ENABLED
              value: "true"
            - name: KC_PROXY_HEADERS
              value: "xforwarded"
            - name: KEYCLOAK_ADMIN
              value: "admin"
            - name: KEYCLOAK_ADMIN_PASSWORD
              value: "admin"
          ports:
            - containerPort: 8080
          resources:
            requests:
              memory: 512Mi
              cpu: 250m
            limits:
              memory: 1Gi
              cpu: 500m
          readinessProbe:
            httpGet:
              path: /realms/master
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 10
            failureThreshold: 10
---
apiVersion: v1
kind: Service
metadata:
  name: keycloak
spec:
  selector:
    app: keycloak
  ports:
    - name: http
      port: 80
      targetPort: 8080
EOF
```

Počkej na spuštění (Keycloak startuje ~30–60 sekund):

```bash
kubectl rollout status deployment/keycloak --timeout=300s
```

---

## 5. Konfigurace Keycloaku přes REST API

Keycloak zpřístupníme dočasně přes port-forward:

```bash
kubectl port-forward svc/keycloak 8090:80 &
```

> Keycloak teď naslouchá na `http://localhost:8090`. Port-forward poběží na pozadí.

### 5.1 Získání admin tokenu

```bash
KC_TOKEN=$(curl -s -X POST http://localhost:8090/realms/master/protocol/openid-connect/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=admin-cli&username=admin&password=admin&grant_type=password" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

### 5.2 Vytvoření realmu `devops-lab`

Realm je izolovaný namespace v Keycloaku – obsahuje uživatele, role a klienty.

```bash
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8090/admin/realms \
  -H "Authorization: Bearer $KC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"realm": "devops-lab", "enabled": true, "displayName": "DevOps Lab"}'
# Očekávaný výstup: 201
```

### 5.3 Vytvoření klienta `portal`

Klient reprezentuje naši aplikaci v Keycloaku. Nastavujeme:
- `publicClient: false` – confidential klient (má secret)
- `standardFlowEnabled: true` – povoluje Authorization Code Flow
- `redirectUris` – kam smí Keycloak přesměrovat po přihlášení

```bash
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8090/admin/realms/devops-lab/clients \
  -H "Authorization: Bearer $KC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "clientId": "portal",
    "enabled": true,
    "protocol": "openid-connect",
    "publicClient": false,
    "standardFlowEnabled": true,
    "directAccessGrantsEnabled": false,
    "redirectUris": ["http://portal.test/callback"],
    "webOrigins": ["http://portal.test"]
  }'
# Očekávaný výstup: 201
```

### 5.4 Získání client secret

```bash
CLIENT_ID=$(curl -s "http://localhost:8090/admin/realms/devops-lab/clients?clientId=portal" \
  -H "Authorization: Bearer $KC_TOKEN" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

CLIENT_SECRET=$(curl -s "http://localhost:8090/admin/realms/devops-lab/clients/$CLIENT_ID/client-secret" \
  -H "Authorization: Bearer $KC_TOKEN" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['value'])")

echo "Client Secret: $CLIENT_SECRET"
```

> Tento secret budeš potřebovat v kroku 6.

### 5.5 Vytvoření rolí

Backend rozlišuje 3 role (z `realm_access.roles` v JWT tokenu):

```bash
for ROLE in viewer developer admin; do
  curl -s -o /dev/null -w "Role $ROLE: %{http_code}\n" \
    -X POST http://localhost:8090/admin/realms/devops-lab/roles \
    -H "Authorization: Bearer $KC_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"$ROLE\"}"
done
```

### 5.6 Vytvoření testovacích uživatelů

```bash
create_user_with_role() {
  local USERNAME=$1
  local PASSWORD=$2
  local ROLE=$3

  curl -s -o /dev/null -w "Create $USERNAME: %{http_code}\n" \
    -X POST http://localhost:8090/admin/realms/devops-lab/users \
    -H "Authorization: Bearer $KC_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$USERNAME\",\"enabled\":true,\"credentials\":[{\"type\":\"password\",\"value\":\"$PASSWORD\",\"temporary\":false}]}"

  USER_ID=$(curl -s "http://localhost:8090/admin/realms/devops-lab/users?username=$USERNAME" \
    -H "Authorization: Bearer $KC_TOKEN" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

  ROLE_ID=$(curl -s "http://localhost:8090/admin/realms/devops-lab/roles/$ROLE" \
    -H "Authorization: Bearer $KC_TOKEN" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

  curl -s -o /dev/null -w "Assign $ROLE to $USERNAME: %{http_code}\n" \
    -X POST "http://localhost:8090/admin/realms/devops-lab/users/$USER_ID/role-mappings/realm" \
    -H "Authorization: Bearer $KC_TOKEN" \
    -H "Content-Type: application/json" \
    -d "[{\"id\":\"$ROLE_ID\",\"name\":\"$ROLE\"}]"
}

create_user_with_role alice Password123 viewer
create_user_with_role bob   Password123 developer
create_user_with_role carol Password123 admin
```

---

## 6. Nasazení backendu přes Helm

```bash
# Vygeneruj bezpečný session secret (64 hex znaků)
SESSION_SECRET=$(openssl rand -hex 32)

helm upgrade --install devops-portal deploy/helm/devops-portal \
  --set image.repository=devops-portal-backend \
  --set image.tag=local \
  --set image.pullPolicy=Never \
  --set secrets.oidcClientSecret=<CLIENT_SECRET_Z_KROKU_5.4> \
  --set secrets.sessionSecret=$SESSION_SECRET
```

> **`imagePullPolicy: Never`** – Kubernetes nebude hledat image ve vzdáleném registry, použije lokálně buildnutý image z minikube Docker daemonu.

Ověření nasazení:

```bash
kubectl rollout status deployment/portal --timeout=60s
kubectl get pods
```

---

## 7. DNS konfigurace na macOS

### Problém

Na macOS (zejména Tahoe / Darwin 26+) `/etc/hosts` není spolehlivě čten pro neznámé TLD jako `.test`. mDNSResponder ho ignoruje.

### Řešení – dnsmasq

`dnsmasq` je lehký DNS server, který dokáže přeložit celou doménu `*.test` na zadanou IP bez nutnosti editovat `/etc/hosts` pro každý hostname.

```bash
# Instalace
brew install dnsmasq

# Wildcard: všechny *.test domény → 127.0.0.1
# (na Apple Silicon je Homebrew v /opt/homebrew)
echo "address=/.test/127.0.0.1" | sudo tee /opt/homebrew/etc/dnsmasq.conf

# Spuštění jako systémová služba
sudo brew services start dnsmasq

# Říct macOS: pro .test TLD se ptej dnsmasq (127.0.0.1:53)
sudo mkdir -p /etc/resolver
echo "nameserver 127.0.0.1" | sudo tee /etc/resolver/test
```

Ověření:

```bash
ping -c 1 portal.test
# Očekávaný výstup: PING portal.test (127.0.0.1)
```

---

## 8. Zpřístupnění aplikace přes minikube tunnel

### Proč je tunnel potřeba?

Minikube na macOS s Docker driverem běží uvnitř Docker kontejneru. Node IP (např. `192.168.49.2`) **není dostupná z macOS hostu** – je to interní Docker síť. `minikube tunnel` vytvoří síťový tunel, který zpřístupní LoadBalancer/Ingress služby na `127.0.0.1`.

```bash
# Spusť v samostatném terminálu – musí běžet celou dobu
minikube tunnel
```

> Vyžádá si `sudo` heslo kvůli privilegovaným portům (80, 443). **Terminál nezavírej** – bez tunelu aplikace přestane být dostupná.

---

## 9. Ověření funkčnosti

```bash
# Backend health check
curl -s http://portal.test/healthz
# Očekáváno: {"ok":true}

# Keycloak realm
curl -s http://auth.portal.test/realms/devops-lab | python3 -m json.tool | head -5
# Očekáváno: JSON s informacemi o realmu

# Přesměrování na login (uživatel není přihlášen)
curl -sv http://portal.test/ 2>&1 | grep "< HTTP"
# Očekáváno: HTTP/1.1 307 Temporary Redirect
```

Nebo otevři v prohlížeči: **http://portal.test**

---

## 10. Testovací účty

| Uživatel | Heslo | Role | Přístup |
|----------|-------|------|---------|
| `alice` | `Password123` | `viewer` | `/`, `/me` |
| `bob` | `Password123` | `developer` | `/`, `/me`, `/dev` |
| `carol` | `Password123` | `admin` | vše včetně `/admin` |

---

## 11. Přehled endpointů

| Endpoint | Popis | Přístup |
|----------|-------|---------|
| `http://portal.test/` | Hlavní stránka | přihlášený uživatel |
| `http://portal.test/login` | Spustí OIDC login flow | veřejný |
| `http://portal.test/callback` | OIDC callback | veřejný |
| `http://portal.test/logout` | Odhlášení | přihlášený uživatel |
| `http://portal.test/me` | Info o přihlášeném uživateli (JSON) | přihlášený uživatel |
| `http://portal.test/dev` | Developer endpoint | `developer`, `admin` |
| `http://portal.test/admin` | Admin endpoint | `admin` |
| `http://portal.test/healthz` | Liveness probe | veřejný |
| `http://portal.test/readyz` | Readiness probe | veřejný |
| `http://auth.portal.test` | Keycloak admin UI | veřejný |

---

## 12. Opravy a known issues

Při nasazení jsme narazili na několik problémů, které vyžadovaly úpravy kódu backendu. Jsou zde zdokumentovány pro reference.

### 12.1 `at_hash` claim validace (auth.py)

**Problém:** Po přihlášení backend vracel `{"detail":"Invalid id_token: No access_token provided to compare against at_hash claim."}`.

**Příčina:** Keycloak zahrnuje v ID tokenu `at_hash` claim – hash access tokenu sloužící jako bezpečnostní kontrola. Původní kód předával do `jwt.decode()` jen `id_token`, ale knihovna `python-jose` potřebuje pro ověření `at_hash` také access token.

**Oprava v `apps/backend/app/auth.py`:**
```python
# Signature funkce doplněna o access_token parametr
async def verify_id_token(id_token: str, access_token: Optional[str] = None) -> Dict[str, Any]:
    ...
    claims = jwt.decode(
        id_token,
        jwks,
        algorithms=["RS256"],
        issuer=issuer,
        audience=OIDC_CLIENT_ID if REQUIRE_AUDIENCE else None,
        access_token=access_token,  # předáme access_token pro at_hash ověření
        options=options,
    )
```

**Oprava v `apps/backend/app/main.py`:**
```python
tokens = await exchange_code_for_tokens(code)
id_token = tokens.get("id_token")
access_token = tokens.get("access_token")  # přidáno
claims = await verify_id_token(id_token, access_token=access_token)  # předáme access_token
```

---

### 12.2 Logout – HTTP 405 Method Not Allowed (main.py)

**Problém:** Po kliknutí na logout backend vrátil "nepodporovaná metoda".

**Příčina:** `RedirectResponse` v FastAPI defaultně používá HTTP 307 (Temporary Redirect), který zachovává HTTP metodu. Backend tak přesměroval `POST /logout` → `POST /`, ale endpoint `/` přijímá pouze `GET`.

**Oprava v `apps/backend/app/main.py`:**
```python
# Před opravou:
resp = RedirectResponse(url="/")  # 307 – zachová POST metodu → 405 na /

# Po opravě:
resp = RedirectResponse(url="...", status_code=303)  # 303 See Other – vždy GET
```

---

### 12.3 Logout neukončoval Keycloak SSO session (main.py)

**Problém:** Po odhlášení z portálu byl uživatel při dalším otevření automaticky přihlášen bez zadání hesla.

**Příčina:** Původní logout pouze smazal session cookie portálu, ale neukončil SSO session v Keycloaku. Keycloak si pamatoval přihlášeného uživatele a při dalším Authorization Code Flow ho rovnou pustil dál.

**Oprava v `apps/backend/app/main.py`:**
```python
@app.post("/logout")
async def logout():
    cfg = await _oidc.load()
    end_session_endpoint = cfg.get("end_session_endpoint")
    resp = RedirectResponse(
        url=f"{end_session_endpoint}?post_logout_redirect_uri=http://portal.test/login&client_id={OIDC_CLIENT_ID}",
        status_code=303,
    )
    clear_session(resp)
    return resp
```

Správný logout flow:
1. Smaže session cookie portálu
2. Přesměruje uživatele na Keycloak `end_session_endpoint`
3. Keycloak ukončí SSO session a přesměruje zpět na `/login`

V Keycloaku bylo také potřeba přidat `http://portal.test/login` jako povolený `post_logout_redirect_uri` v nastavení klienta `portal`.

---

### 12.4 OIDC_ISSUER – interní vs. veřejná URL

**Problém:** Backend používal interní cluster URL `http://keycloak/realms/devops-lab` jako `OIDC_ISSUER`. Keycloak vracel `authorization_endpoint` s hostname `keycloak` – prohlížeč uživatele tuto adresu nezná.

**Příčina:** Keycloak generuje URL v discovery dokumentu (`/.well-known/openid-configuration`) na základě `Host` hlavičky requestu. Když se backend ptal přes `http://keycloak/...`, Keycloak odpovídal s `http://keycloak/...` v URL.

**Řešení:**
1. Nastavit `KC_HOSTNAME=auth.portal.test` na Keycloak deploymentu – Keycloak vždy vrací veřejnou URL bez ohledu na Host hlavičku requestu.
2. Přidat `hostAliases` do backend podu, aby `auth.portal.test` překládal na ClusterIP keycloak service – backend tak může dosáhnout Keycloak přes veřejnou URL i uvnitř clusteru.
3. Nastavit `OIDC_ISSUER=http://auth.portal.test/realms/devops-lab` (veřejná URL).

```bash
# Nastavení KC_HOSTNAME na Keycloak deploymentu
kubectl set env deployment/keycloak KC_HOSTNAME=auth.portal.test KC_HOSTNAME_STRICT=false
```

`values.yaml` přidáno:
```yaml
keycloakHostAlias:
  enabled: true
  ip: "10.109.239.81"  # ClusterIP of keycloak service
```

`backend.yaml` (Helm template) přidáno:
```yaml
hostAliases:
  - ip: {{ .Values.keycloakHostAlias.ip }}
    hostnames:
      - {{ .Values.ingress.keycloakHost }}
```

---

## 13. Časté problémy

### DNS nefunguje (`Could not resolve host: portal.test`)

1. Ověř, že dnsmasq běží: `brew services list | grep dnsmasq`
2. Ověř `/etc/resolver/test`: `cat /etc/resolver/test` → má obsahovat `nameserver 127.0.0.1`
3. Zkus restartovat dnsmasq: `sudo brew services restart dnsmasq`

### Aplikace není dostupná po restartu Macu

`minikube tunnel` se po restartu nezachová. Po každém restartu:

```bash
minikube start
minikube tunnel   # v samostatném terminálu
```

### Keycloak ztratil konfiguraci po restartu podu

Keycloak v `start-dev` módu používá **H2 in-memory databázi** – data se ztratí při restartu podu. Pro perzistenci je potřeba přidat PostgreSQL a nastavit `KC_DB=postgres`. Pro lokální vývoj je nejjednodušší uložit si konfigurační skripty z kroku 5 a spustit je znovu.

### Backend se nepřipojí ke Keycloaku (`OIDC discovery failed`)

Backend se připojuje ke Keycloaku uvnitř clusteru přes `http://keycloak/` (cluster DNS). Ověř:

```bash
kubectl exec deployment/portal -- curl -s http://keycloak/realms/devops-lab | head -c 100
```

### `ErrImagePull` pro Keycloak

Bitnami Helm chart má od srpna 2025 omezené images – použij místo toho přímý manifest s `quay.io/keycloak/keycloak:26.1` (viz krok 4).

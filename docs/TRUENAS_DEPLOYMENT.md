# TrueNAS Deployment Guide

Deploys the FastAPI server as a custom Docker Compose app on TrueNAS SCALE (Goldeye / 25.10+).
The app runs behind a Caddy reverse proxy with TLS on host port **8443**, accessible at
`https://<your-domain>:8443`.

---

## Prerequisites

- TrueNAS SCALE 25.10 or later
- A domain name with an A record pointing to `10.1.1.204` (e.g. `api.example.com`)
- The Docker image has been built and pushed to GHCR (see [Build the image](#1-build-the-image))
- The GHCR package is set to **Public** (see [Make the package public](#2-make-the-ghcr-package-public))

---

## 1. Build the image

The GitHub Actions workflow at `.github/workflows/docker-publish.yml` builds and pushes
`ghcr.io/elured-code/traveller-world-gen:latest` automatically on every push to `main` or `v1.5.0`.

To trigger a build manually:

1. Go to **github.com/Elured-code/traveller-world-gen → Actions**
2. Select **Build and push Docker image**
3. Click **Run workflow**, choose the branch, click **Run workflow**
4. Wait for the run to show a green checkmark (~3–5 minutes)

---

## 2. Make the GHCR package public

By default GHCR packages are private. TrueNAS needs unauthenticated pull access.

1. Go to **github.com/Elured-code → Packages**
2. Click **traveller-world-gen**
3. Click **Package settings** (bottom-right)
4. Scroll to **Danger Zone → Change visibility**
5. Set to **Public** and confirm

> If you prefer to keep the package private, add a GHCR pull secret to the Docker Compose
> (see [Private image pull](#private-image-pull) below).

---

## 3. Set your domain in the compose file

Edit `deploy/docker-compose.truenas.yml` and replace every occurrence of `YOUR_DOMAIN_HERE`
with your actual domain (e.g. `api.example.com`). There are two occurrences: one in the port
comment and one in the embedded Caddyfile.

The domain's DNS A record must resolve to `10.1.1.204` before the first deploy.

---

## 4. Deploy on TrueNAS

TrueNAS 25.10 has two custom app options in the Discover Apps screen. Use **Install via YAML**
(not "Custom App") to get the Docker Compose editor.

### 4a. Open the Apps section

1. In the TrueNAS web UI, click **Apps** in the left sidebar
2. Click **Discover Apps**
3. Click **Install via YAML** (top-right of the Discover Apps screen)

### 4b. Configure the app

| Field | Value |
|---|---|
| Application Name | `traveller-api` |

In the **Custom Config** field, paste the contents of `deploy/docker-compose.truenas.yml`
(with `YOUR_DOMAIN_HERE` already replaced with your domain):

```yaml
services:
  traveller-api:
    image: ghcr.io/elured-code/traveller-world-gen:latest
    restart: unless-stopped
    environment:
      RATE_LIMIT_PER_MINUTE: "100/minute"
      TRAVELLER_MAX_BATCH_SIZE: "20"

  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "8443:443"
      - "8080:80"
    volumes:
      - caddy_data:/data
      - caddy_config:/config
    configs:
      - source: caddyfile
        target: /etc/caddy/Caddyfile

configs:
  caddyfile:
    content: |
      api.example.com {
          tls internal
          reverse_proxy traveller-api:8000
      }

volumes:
  caddy_data:
  caddy_config:
```

Click **Install**. TrueNAS will pull both images and start the containers (~1–2 minutes on first run).

---

## 5. Verify

Once the app shows **Running** in the Apps list, test it:

```bash
# -k skips cert verification (expected until you trust the CA — see step 6)
curl -k https://api.example.com:8443/api/world?seed=42
curl -k https://api.example.com:8443/api/system?seed=42

# HTTP should redirect to HTTPS automatically
curl -v http://api.example.com:8080/
```

The web UI is available at: `https://api.example.com:8443`

> **TrueNAS port note:** TrueNAS's own web UI uses ports 80 and 443, so the API is on
> **8443** (HTTPS) and **8080** (HTTP redirect). If you change TrueNAS's UI to a different
> port, you can update the compose to use `443:443` and `80:80` instead.

---

## 6. Trust Caddy's root CA (optional — eliminates browser warnings)

Caddy's `tls internal` issues certs from its own local CA. Browsers will warn until you
install that CA cert as trusted on each client device.

### Export the root cert

On TrueNAS, open a shell (via the TrueNAS UI → System → Shell) and run:

```bash
docker exec $(docker ps -qf name=traveller-api_caddy) \
  cat /data/caddy/pki/authorities/local/root.crt > /tmp/caddy-root.crt
```

Then copy `/tmp/caddy-root.crt` to your client machine.

### Install on macOS

```bash
sudo security add-trusted-cert -d -r trustRoot \
  -k /Library/Keychains/System.keychain caddy-root.crt
```

### Install on Windows

Double-click `caddy-root.crt` → **Install Certificate** → **Local Machine** →
**Trusted Root Certification Authorities**.

### Install on iOS / iPadOS

AirDrop the `.crt` file to your device, then go to
**Settings → General → VPN & Device Management → Install** and then enable full trust in
**Settings → General → About → Certificate Trust Settings**.

---

## 7. Updating to a new image

After a new build is pushed to GHCR:

1. Go to **Apps** in the TrueNAS web UI
2. Click the **traveller-api** app
3. Click **Update** (if TrueNAS detects a newer digest) — or click **Edit**, make no changes, and click **Save** to force a re-pull

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `RATE_LIMIT_PER_MINUTE` | `100/minute` | SlowAPI per-IP rate limit |
| `TRAVELLER_MAX_BATCH_SIZE` | `20` | Maximum worlds per `/api/worlds` batch request |

---

## Switching to Let's Encrypt (future)

Once your DNS provider is known, replace `tls internal` in the embedded Caddyfile with:

```
tls {
    dns <provider> {env.DNS_API_TOKEN}
}
```

Add `DNS_API_TOKEN` to the Caddy service's `environment:` block, and switch to a Caddy image
that includes the DNS plugin (e.g. `ghcr.io/elured-code/caddy-cloudflare:latest` built with
`xcaddy build --with github.com/caddy-dns/cloudflare`). Common providers: `cloudflare`,
`route53`.

---

## Private image pull

If the GHCR package is private, add registry credentials to the compose:

```yaml
services:
  traveller-api:
    image: ghcr.io/elured-code/traveller-world-gen:latest
    restart: unless-stopped
    environment:
      RATE_LIMIT_PER_MINUTE: "100/minute"
      TRAVELLER_MAX_BATCH_SIZE: "20"

# Pre-login on TrueNAS shell before deploying:
# docker login ghcr.io -u <github-username> -p <personal-access-token>
```

Generate a GitHub Personal Access Token with `read:packages` scope at
**github.com → Settings → Developer settings → Personal access tokens**.

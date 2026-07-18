# Stratum AI — Operator Runbook

A one-page reference for installing and running your Stratum AI instance.
For the full detail behind any step, see `INSTALL.md`.

---

## 1. Before you start — checklist

- [ ] A Linux server (Ubuntu-like), on the public internet, **≥ 4 GB RAM / 2 vCPUs** (8 GB / 4 vCPUs recommended).
- [ ] **Docker + Compose** installed → `curl -fsSL https://get.docker.com | sh`
- [ ] A **domain** (e.g. `app.yourcompany.com`) with a **DNS A record pointing at this server's IP** — set this up *first*, or the HTTPS certificate can't be issued.
- [ ] **Ports 80 and 443 open** inbound (firewall / cloud security group). Nothing else is needed.
- [ ] Login details for the **image registry** your vendor gave you (the installer will run `docker login` for you).
- [ ] The **installer kit** file from your vendor (`stratum-deploy-kit.tar.gz`).

---

## 2. Install (one command)

```bash
tar xzf stratum-deploy-kit.tar.gz && cd deploy
./install.sh
```

The installer asks for your **domain**, **admin email**, and **registry**, then does the rest automatically — it generates every password and security key itself (you never invent or type them), pulls the app, starts everything, and waits until it's healthy.

**No prompts?** Run it non-interactively:
```bash
./install.sh --domain app.yourcompany.com --email owner@yourcompany.com \
             --registry ghcr.io/your-vendor --non-interactive
```

When it finishes it prints your **URL, admin email, and admin password** (also saved to `.installer-secrets/superadmin-password.txt`). **Keep that password safe.**

---

## 3. First login

1. Open `https://<your-domain>` and log in with the admin email + password from step 2.
2. Complete the one-time setup wizard.
3. Go to **Settings → Integrations** to connect your ad platforms (Meta, Google Ads, TikTok, Snapchat) and other tools — all done in the browser. You never need server access or to edit files to connect an account.

---

## 4. Everyday operations

All commands run from the `deploy/` folder.

| Task | Command |
|---|---|
| **Upgrade** to the latest version | `./install.sh --upgrade` *(pulls new images, restarts; your data + settings untouched)* |
| **Check health** | `curl -I https://<your-domain>/health` → expect `200 OK` |
| **Check services** | `docker compose -f docker-compose.client.yml ps` → all should read `healthy` |
| **View logs** | `docker compose -f docker-compose.client.yml logs -f api` *(or omit `api` for everything)* |
| **Restart one service** | `docker compose -f docker-compose.client.yml restart api` |
| **Back up the database** | `docker compose -f docker-compose.client.yml exec db pg_dump -U stratum stratum_ai \| gzip > backup-$(date +%F).sql.gz` |

**Include in your backups:** the `postgres_data` volume (the database — the backup command covers it), `asset_uploads` (uploaded creatives), and `caddy_data` (your TLS certificate). List volumes with `docker volume ls | grep deploy`.

---

## 5. If something's wrong

- **Site shows "not secure" / no certificate** → your domain's DNS A record isn't resolving to this server yet, or ports 80/443 aren't reachable. Confirm with `dig +short <your-domain>` from another machine, check `docker compose -f docker-compose.client.yml logs caddy`, wait for DNS to propagate, then re-run `./install.sh`.
- **A service keeps restarting** → `docker compose -f docker-compose.client.yml logs --tail=200 <service>`. Usually a mistyped `.env` value (watch for trailing spaces) or the database still starting.
- **App won't respond** → `docker compose -f docker-compose.client.yml ps` to find the unhealthy service, then read its logs.

---

## ⚠️ One safety rule — `SEED_SUPERADMIN`

To change your admin password in normal use, just do it **in-app** (Settings → Account). Only if you're fully locked out:

1. In `.env`, set a new `SUPERADMIN_PASSWORD` (16+ chars) and `SEED_SUPERADMIN=true`.
2. `docker compose -f docker-compose.client.yml up -d api`, wait until healthy.
3. **Set `SEED_SUPERADMIN=false` again.** ← Do not skip this. Left on, it overwrites the admin password on *every* restart, silently undoing any password you set in-app. (`install.sh` turns it off for you after a normal install; this reset is the only time you'd touch it.)

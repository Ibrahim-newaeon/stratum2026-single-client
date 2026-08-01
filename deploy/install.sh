#!/usr/bin/env bash
# =============================================================================
# ADs Growth System - Client Installer
# -----------------------------------------------------------------------------
# One-command installer for a single-client ADs Growth System deployment. Run this
# from inside the extracted deploy kit (the directory containing this script,
# docker-compose.client.yml, Caddyfile, init-db.sql, and .env.client.example).
#
# Usage:
#   ./install.sh [options]
#   ./install.sh --upgrade
#
# Options:
#   --domain DOMAIN         Client domain (DNS A record must already point here)
#   --email EMAIL           Superadmin login email
#   --admin-password PASS   Superadmin password (16+ chars). Omit to auto-generate.
#   --registry URL          Container registry the images are pulled from
#   --version TAG           Image tag to deploy (default: latest)
#   --non-interactive        Never prompt; fail if a required value is missing
#   --skip-login             Don't offer a `docker login` prompt
#   --skip-smtp               Don't prompt for SMTP password
#   --force                   Overwrite an existing .env (regenerates secrets)
#   --upgrade                  Pull new images and restart; no prompts, .env untouched
#   -h, --help                 Show this help
#
# Safe to re-run: without --force, an existing .env is reused as-is and no
# secrets are regenerated.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

COMPOSE_FILE="docker-compose.client.yml"
ENV_FILE=".env"
ENV_EXAMPLE=".env.client.example"
SECRETS_DIR=".installer-secrets"

# -----------------------------------------------------------------------------
# Defaults / flags
# -----------------------------------------------------------------------------
OPT_DOMAIN=""
OPT_EMAIL=""
OPT_ADMIN_PASSWORD=""
OPT_REGISTRY=""
OPT_VERSION="latest"
NON_INTERACTIVE=false
SKIP_LOGIN=false
SKIP_SMTP=false
FORCE=false
UPGRADE=false

# -----------------------------------------------------------------------------
# Output helpers
# -----------------------------------------------------------------------------
c_bold=""; c_green=""; c_yellow=""; c_red=""; c_reset=""
if [ -t 1 ]; then
    c_bold="\033[1m"; c_green="\033[32m"; c_yellow="\033[33m"; c_red="\033[31m"; c_reset="\033[0m"
fi
info()  { printf "%b\n" "${c_bold}==>${c_reset} $*"; }
warn()  { printf "%b\n" "${c_yellow}WARNING:${c_reset} $*" >&2; }
error() { printf "%b\n" "${c_red}ERROR:${c_reset} $*" >&2; }
die()   { error "$*"; exit 1; }

usage() {
    sed -n '2,28p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

# -----------------------------------------------------------------------------
# Arg parsing
# -----------------------------------------------------------------------------
while [ $# -gt 0 ]; do
    case "$1" in
        --domain) OPT_DOMAIN="$2"; shift 2 ;;
        --email) OPT_EMAIL="$2"; shift 2 ;;
        --admin-password) OPT_ADMIN_PASSWORD="$2"; shift 2 ;;
        --registry) OPT_REGISTRY="$2"; shift 2 ;;
        --version) OPT_VERSION="$2"; shift 2 ;;
        --non-interactive) NON_INTERACTIVE=true; shift ;;
        --skip-login) SKIP_LOGIN=true; shift ;;
        --skip-smtp) SKIP_SMTP=true; shift ;;
        --force) FORCE=true; shift ;;
        --upgrade) UPGRADE=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) die "Unknown option: $1 (see --help)" ;;
    esac
done

# -----------------------------------------------------------------------------
# Preflight checks
# -----------------------------------------------------------------------------
check_docker() {
    command -v docker >/dev/null 2>&1 || die "docker is not installed. See https://docs.docker.com/engine/install/ then re-run this script."
    docker compose version >/dev/null 2>&1 || die "docker compose (v2 plugin) is not available. Install the 'docker-compose-plugin' package, then re-run this script."
}

check_privileges() {
    if [ "$(id -u)" -eq 0 ]; then
        return 0
    fi
    if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
        return 0
    fi
    warn "Not running as root and the current user cannot talk to the Docker daemon."
    warn "Re-run as root, with sudo, or add your user to the 'docker' group (newgrp docker) first."
}

check_ports() {
    local busy=""
    for port in 80 443; do
        if command -v ss >/dev/null 2>&1; then
            ss -ltn 2>/dev/null | awk '{print $4}' | grep -q ":${port}\$" && busy="${busy} ${port}"
        elif command -v netstat >/dev/null 2>&1; then
            netstat -ltn 2>/dev/null | awk '{print $4}' | grep -q ":${port}\$" && busy="${busy} ${port}"
        fi
    done
    if [ -n "$busy" ]; then
        warn "Port(s)${busy} already appear to be in use. Caddy will fail to bind them unless whatever is using them is stopped first."
    fi
}

# -----------------------------------------------------------------------------
# Secret generation
# -----------------------------------------------------------------------------
gen_secret() { openssl rand -base64 32 | tr -d '\n'; }
gen_password() { openssl rand -base64 24 | tr -d '\n'; }

# Escapes a value for safe use as a sed replacement (delimiter '|').
sed_escape() { printf '%s' "$1" | sed -e 's/[\\|&]/\\&/g'; }

set_env_var() {
    # set_env_var KEY VALUE FILE
    local key="$1" value="$2" file="$3"
    local escaped
    escaped="$(sed_escape "$value")"
    if grep -q "^${key}=" "$file"; then
        sed -i "s|^${key}=.*|${key}=${escaped}|" "$file"
    else
        printf '%s=%s\n' "$key" "$value" >> "$file"
    fi
}

prompt() {
    # prompt VAR_NAME "Question" "default"
    local __var="$1" question="$2" default="${3:-}" input
    if [ "$NON_INTERACTIVE" = true ]; then
        eval "$__var=\"\$default\""
        return
    fi
    if [ -n "$default" ]; then
        read -r -p "$question [$default]: " input || true
    else
        read -r -p "$question: " input || true
    fi
    input="${input:-$default}"
    eval "$__var=\"\$input\""
}

prompt_secret() {
    # prompt_secret VAR_NAME "Question"
    local __var="$1" question="$2" input
    if [ "$NON_INTERACTIVE" = true ]; then
        eval "$__var=\"\""
        return
    fi
    read -r -s -p "$question: " input || true
    printf "\n"
    eval "$__var=\"\$input\""
}

# -----------------------------------------------------------------------------
# Upgrade path
# -----------------------------------------------------------------------------
do_upgrade() {
    [ -f "$ENV_FILE" ] || die "No .env found at $SCRIPT_DIR/.env — run ./install.sh (without --upgrade) first."
    check_docker
    info "Pulling latest images..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" pull
    info "Restarting stack..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d
    wait_for_health
    info "Upgrade complete."
    exit 0
}

# -----------------------------------------------------------------------------
# Health wait
# -----------------------------------------------------------------------------
wait_for_health() {
    local domain
    domain="$(grep '^STRATUM_DOMAIN=' "$ENV_FILE" | cut -d= -f2-)"
    local timeout=180
    local elapsed=0
    local interval=5
    info "Waiting for the stack to become healthy (timeout: ${timeout}s)..."
    while [ "$elapsed" -lt "$timeout" ]; do
        if [ -n "$domain" ] && curl -fsSk "https://${domain}/health" >/dev/null 2>&1; then
            info "Health check passed at https://${domain}/health"
            return 0
        fi
        if curl -fs "http://localhost/health" >/dev/null 2>&1; then
            info "Health check passed at http://localhost/health (via Caddy)"
            return 0
        fi
        sleep "$interval"
        elapsed=$((elapsed + interval))
    done
    warn "Timed out waiting for /health after ${timeout}s. The stack may still be starting (DNS propagation and first-boot migrations can take a few minutes)."
    warn "Check status with: docker compose -f $COMPOSE_FILE logs -f"
    warn "Leaving SEED_SUPERADMIN=true in $ENV_FILE so the next 'docker compose ... up -d' retries seeding the admin account. Re-run './install.sh' (or 'docker compose -f $COMPOSE_FILE --env-file $ENV_FILE up -d') once the stack is reachable."
    return 1
}

# -----------------------------------------------------------------------------
# One-shot seed flag: flip SEED_SUPERADMIN back off once the stack is
# confirmed healthy, so the owner's password_hash is never force-reverted by
# a later `api` restart. Idempotent — safe to call even if already false.
# -----------------------------------------------------------------------------
disable_seed_superadmin() {
    sed -i "s|^SEED_SUPERADMIN=.*|SEED_SUPERADMIN=false|" "$ENV_FILE"
    info "First-boot admin seeding complete — set SEED_SUPERADMIN=false in $ENV_FILE."
}

# -----------------------------------------------------------------------------
# Fresh install / rerun
# -----------------------------------------------------------------------------
do_install() {
    check_docker
    check_privileges
    check_ports

    [ -f "$COMPOSE_FILE" ] || die "$COMPOSE_FILE not found in $SCRIPT_DIR — run this script from inside the deploy kit."
    [ -f "$ENV_EXAMPLE" ] || die "$ENV_EXAMPLE not found in $SCRIPT_DIR."

    if [ -f "$ENV_FILE" ] && [ "$FORCE" != true ]; then
        info "Existing .env found — reusing it (pass --force to regenerate)."
    else
        info "Writing new .env from $ENV_EXAMPLE..."
        cp "$ENV_EXAMPLE" "$ENV_FILE"

        prompt OPT_DOMAIN "Client domain (must already resolve to this server)" "$OPT_DOMAIN"
        [ -n "$OPT_DOMAIN" ] || die "A domain is required (--domain or interactive prompt)."

        prompt OPT_EMAIL "Superadmin login email" "$OPT_EMAIL"
        [ -n "$OPT_EMAIL" ] || die "A superadmin email is required (--email or interactive prompt)."

        prompt OPT_REGISTRY "Container registry (e.g. ghcr.io/your-org)" "$OPT_REGISTRY"
        [ -n "$OPT_REGISTRY" ] || die "A registry is required (--registry or interactive prompt)."

        if [ "$SKIP_LOGIN" != true ] && [ "$NON_INTERACTIVE" != true ]; then
            local do_login
            read -r -p "Log in to '$OPT_REGISTRY' now? [y/N]: " do_login || true
            case "$do_login" in
                y|Y|yes|YES) docker login "$OPT_REGISTRY" || warn "docker login failed — you can retry manually before 'docker compose pull'." ;;
            esac
        fi

        local generated_password=false
        if [ -z "$OPT_ADMIN_PASSWORD" ]; then
            prompt_secret OPT_ADMIN_PASSWORD "Superadmin password (leave blank to auto-generate)"
        fi
        if [ -z "$OPT_ADMIN_PASSWORD" ]; then
            OPT_ADMIN_PASSWORD="$(gen_password)"
            generated_password=true
        fi
        if [ "${#OPT_ADMIN_PASSWORD}" -lt 16 ]; then
            die "Superadmin password must be at least 16 characters."
        fi

        local smtp_password=""
        if [ "$SKIP_SMTP" != true ]; then
            prompt_secret smtp_password "SMTP password (optional, press Enter to skip)"
        fi

        info "Generating secrets..."
        local secret_key jwt_secret pii_key pg_password redis_password whatsapp_verify metrics_api_key
        secret_key="$(gen_secret)"
        jwt_secret="$(gen_secret)"
        pii_key="$(gen_secret)"
        pg_password="$(gen_password)"
        redis_password="$(gen_password)"
        whatsapp_verify="$(gen_secret)"
        metrics_api_key="$(gen_secret)"

        set_env_var "STRATUM_DOMAIN" "$OPT_DOMAIN" "$ENV_FILE"
        set_env_var "FRONTEND_URL" "https://${OPT_DOMAIN}" "$ENV_FILE"
        set_env_var "CORS_ORIGINS" "https://${OPT_DOMAIN}" "$ENV_FILE"
        set_env_var "OAUTH_REDIRECT_BASE_URL" "https://${OPT_DOMAIN}" "$ENV_FILE"
        set_env_var "STRATUM_REGISTRY" "$OPT_REGISTRY" "$ENV_FILE"
        set_env_var "STRATUM_VERSION" "$OPT_VERSION" "$ENV_FILE"
        set_env_var "SUPERADMIN_EMAIL" "$OPT_EMAIL" "$ENV_FILE"
        set_env_var "SUPERADMIN_PASSWORD" "$OPT_ADMIN_PASSWORD" "$ENV_FILE"
        set_env_var "SECRET_KEY" "$secret_key" "$ENV_FILE"
        set_env_var "JWT_SECRET_KEY" "$jwt_secret" "$ENV_FILE"
        set_env_var "PII_ENCRYPTION_KEY" "$pii_key" "$ENV_FILE"
        set_env_var "POSTGRES_PASSWORD" "$pg_password" "$ENV_FILE"
        set_env_var "REDIS_PASSWORD" "$redis_password" "$ENV_FILE"
        set_env_var "WHATSAPP_VERIFY_TOKEN" "$whatsapp_verify" "$ENV_FILE"
        set_env_var "METRICS_API_KEY" "$metrics_api_key" "$ENV_FILE"
        if [ -n "$smtp_password" ]; then
            set_env_var "SMTP_PASSWORD" "$smtp_password" "$ENV_FILE"
        fi
        # One-shot seed: true for this first boot only. wait_for_health (below)
        # flips this back to false once the health check confirms the owner
        # user was seeded — see docker-compose.client.yml's SEED_SUPERADMIN
        # comment and INSTALL.md's password-reset section. If left on, any
        # password the client changes in-app would be silently reverted on
        # every subsequent api restart.
        set_env_var "SEED_SUPERADMIN" "true" "$ENV_FILE"
        chmod 600 "$ENV_FILE"

        if [ "$generated_password" = true ]; then
            mkdir -p "$SECRETS_DIR"
            chmod 700 "$SECRETS_DIR"
            printf '%s\n' "$OPT_ADMIN_PASSWORD" > "$SECRETS_DIR/superadmin-password.txt"
            chmod 600 "$SECRETS_DIR/superadmin-password.txt"
        fi
    fi

    info "Pulling images..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" pull

    info "Starting the stack..."
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d

    if wait_for_health; then
        disable_seed_superadmin
    fi

    print_success_box
}

print_success_box() {
    local domain email pass_note
    domain="$(grep '^STRATUM_DOMAIN=' "$ENV_FILE" | cut -d= -f2-)"
    email="$(grep '^SUPERADMIN_EMAIL=' "$ENV_FILE" | cut -d= -f2-)"
    if [ -f "$SECRETS_DIR/superadmin-password.txt" ]; then
        pass_note="printed once below, and saved to $SCRIPT_DIR/$SECRETS_DIR/superadmin-password.txt (delete this file once you've saved the password elsewhere)"
    else
        pass_note="the one you entered during setup"
    fi
    printf "\n"
    printf "%b\n" "${c_green}============================================================${c_reset}"
    printf "%b\n" "${c_green}  ADs Growth System is installed${c_reset}"
    printf "%b\n" "${c_green}============================================================${c_reset}"
    printf "  URL:           https://%s\n" "$domain"
    printf "  Admin email:   %s\n" "$email"
    printf "  Admin password: %s\n" "$pass_note"
    if [ -f "$SECRETS_DIR/superadmin-password.txt" ]; then
        printf "\n  Password: %s\n" "$(cat "$SECRETS_DIR/superadmin-password.txt")"
    fi
    printf "\n"
    printf "  Log in and complete the setup wizard.\n"
    printf "%b\n" "${c_green}============================================================${c_reset}"
    printf "\n"
}

# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------
if [ "$UPGRADE" = true ]; then
    do_upgrade
else
    do_install
fi

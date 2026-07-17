#!/usr/bin/env bash
# =============================================================================
# Stratum AI - Vendor Build & Push
# -----------------------------------------------------------------------------
# VENDOR-SIDE ONLY. Builds the two domain-generic images that every client
# deployment pulls (see docker-compose.client.yml) and pushes them to a
# private registry. Run from the repository root:
#
#   ./deploy/build-and-push.sh REGISTRY [VERSION]
#
# Example:
#   ./deploy/build-and-push.sh ghcr.io/your-org 1.4.0
#
# REGISTRY  - registry + namespace images are pushed under, e.g.
#             ghcr.io/your-org or registry.example.com/stratum
# VERSION   - optional image tag (default: derived from `git describe`, or
#             "dev" if that fails). Images are always ALSO tagged :latest.
#
# The frontend image is built once with VITE_API_URL=/api/v1 and
# VITE_WS_URL="" baked in — every client's Caddy proxies the same domain to
# both api and frontend, so the SPA's relative API base and same-origin
# WebSocket fallback (frontend/src/api/client.ts,
# frontend/src/hooks/useWebSocket.ts:32-33) work unmodified for any client.
# There is exactly one frontend image and one backend image; clients never
# get a per-domain rebuild.
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

REGISTRY="${1:-}"
if [ -z "$REGISTRY" ]; then
    echo "Usage: $0 REGISTRY [VERSION]" >&2
    echo "Example: $0 ghcr.io/your-org 1.4.0" >&2
    exit 1
fi
REGISTRY="${REGISTRY%/}"

VERSION="${2:-}"
if [ -z "$VERSION" ]; then
    VERSION="$(git describe --tags --always --dirty 2>/dev/null || echo dev)"
fi

BACKEND_IMAGE="${REGISTRY}/stratum-backend"
FRONTEND_IMAGE="${REGISTRY}/stratum-frontend"

echo "==> Registry: $REGISTRY"
echo "==> Version tag: $VERSION"
echo "==> Backend image: ${BACKEND_IMAGE}:${VERSION} (also tagged :latest)"
echo "==> Frontend image: ${FRONTEND_IMAGE}:${VERSION} (also tagged :latest)"
echo

echo "==> Building backend image from ./backend ..."
docker build \
    -t "${BACKEND_IMAGE}:${VERSION}" \
    -t "${BACKEND_IMAGE}:latest" \
    ./backend
echo "==> Backend image built."
echo

echo "==> Building frontend image from ./frontend (domain-generic: VITE_API_URL=/api/v1, VITE_WS_URL=<empty>) ..."
docker build \
    --target production \
    --build-arg VITE_API_URL=/api/v1 \
    --build-arg VITE_WS_URL= \
    -t "${FRONTEND_IMAGE}:${VERSION}" \
    -t "${FRONTEND_IMAGE}:latest" \
    ./frontend
echo "==> Frontend image built."
echo

echo "==> Pushing backend image tags..."
docker push "${BACKEND_IMAGE}:${VERSION}"
docker push "${BACKEND_IMAGE}:latest"

echo "==> Pushing frontend image tags..."
docker push "${FRONTEND_IMAGE}:${VERSION}"
docker push "${FRONTEND_IMAGE}:latest"

echo
echo "==> Done. Clients deploy with:"
echo "    STRATUM_REGISTRY=${REGISTRY}"
echo "    STRATUM_VERSION=${VERSION}  (or 'latest')"

"""Production docs gate.

`/docs`, `/redoc` and `/openapi.json` are meant to be api-key gated in
production (`verify_docs_access`). They were not. Two defects compounded:

1. FastAPI was always constructed with `docs_url="/docs"` etc., so it
   registered its built-in docs routes. The gated routes were appended
   afterwards at the same paths, and Starlette matches in route order — so the
   built-in always won and the gate never executed, even with DOCS_API_KEY
   set. `app.routes` genuinely held two entries for `/docs`
   (`Route swagger_ui_html`, then `APIRoute custom_docs`).
2. The gate itself returned early when DOCS_API_KEY was unset, so even had it
   been reachable it would have failed open.

Production ran with DOCS_API_KEY unset, so `/openapi.json` served all 606
paths unauthenticated on the public Railway host.

These tests pin the route wiring rather than HTTP behaviour: the wiring is
what broke, it is cheap to assert, and it needs no live settings swap. Both
were confirmed to fail against the pre-fix code.
"""

import pytest

pytestmark = pytest.mark.unit

DOC_PATHS = ("/docs", "/redoc", "/openapi.json")


def _paths(app):
    return [getattr(r, "path", None) for r in app.routes]


def test_production_registers_no_builtin_docs_routes(monkeypatch):
    """In production the built-ins must be absent so the gate can bind.

    A duplicate here is the exact shape of the original bug: two routes on one
    path, the ungated one first.
    """
    from app.core.config import settings

    monkeypatch.setattr(type(settings), "is_production", property(lambda _: True))
    from app.main import create_application

    app = create_application()
    paths = _paths(app)

    for doc_path in DOC_PATHS:
        count = paths.count(doc_path)
        assert count <= 1, (
            f"{doc_path} is registered {count} times in production. FastAPI's "
            "built-in docs route is shadowing the api-key-gated one, so the "
            "gate never runs. Pass docs_url/redoc_url/openapi_url=None when "
            "settings.is_production."
        )

    # The gated handlers should be the ones bound.
    for route in app.routes:
        if getattr(route, "path", None) in DOC_PATHS:
            name = getattr(getattr(route, "endpoint", None), "__name__", "")
            assert name.startswith("custom_"), (
                f"{route.path} is served by {name!r}, not the gated handler. "
                "Only custom_docs / custom_redoc / custom_openapi enforce "
                "verify_docs_access."
            )


def test_non_production_keeps_docs_open(monkeypatch):
    """Dev and test must keep working docs — the gate is production-only."""
    from app.core.config import settings

    monkeypatch.setattr(type(settings), "is_production", property(lambda _: False))
    from app.main import create_application

    app = create_application()
    paths = _paths(app)

    for doc_path in DOC_PATHS:
        assert doc_path in paths, (
            f"{doc_path} disappeared outside production. Gating must not cost "
            "local and CI environments their API docs."
        )

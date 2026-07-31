"""OpenAPI schema generation guard.

Nothing in the suite exercised ``/openapi.json`` before this module, which is
how a single route shipped with ``response_class=None`` and silently took the
whole schema document down — and with it ``/docs`` and ``/redoc``, since both
fetch the schema at load time. The route itself kept returning 200, so no
endpoint test noticed.

FastAPI asserts on the response class while building the document
(``fastapi/openapi/utils.py``: "A response class is needed to generate
OpenAPI"). The assert is per-route but the blast radius is the entire schema:
one bad route means no API docs at all.

The guard is deliberately the real ``app.openapi()`` call rather than a
hand-rolled walk of ``app.routes``. FastAPI 0.140 stopped flattening included
routers into ``app.routes`` — they sit behind an internal ``_IncludedRouter``
whose children resolve through ContextVars — so any traversal we wrote here
would inspect only top-level routes and pass while the bug was present. That
exact false negative was observed while writing this test. Calling the code
path FastAPI actually serves keeps the guard correct across upgrades.
"""

import pytest

pytestmark = pytest.mark.unit


def _capture_failing_route(monkeypatch):
    """Best-effort: record which route aborts schema generation.

    ``get_openapi_path`` is a private helper, so this is diagnostics only —
    if FastAPI renames it, we lose the route name but still fail on the
    schema build itself. Never let the instrumentation decide the verdict.
    """
    import fastapi.openapi.utils as openapi_utils

    captured: list[str] = []
    original = getattr(openapi_utils, "get_openapi_path", None)
    if original is None:  # pragma: no cover - depends on FastAPI internals
        return captured

    def instrumented(*args, **kwargs):
        route = kwargs.get("route") or (args[0] if args else None)
        try:
            return original(*args, **kwargs)
        except AssertionError:
            methods = sorted(getattr(route, "methods", None) or [])
            captured.append(
                f"{methods} {getattr(route, 'path', '<unknown path>')} "
                f"(response_class={getattr(route, 'response_class', '<missing>')!r})"
            )
            raise

    monkeypatch.setattr(openapi_utils, "get_openapi_path", instrumented)
    return captured


def test_openapi_schema_generates(monkeypatch):
    """The full OpenAPI document must build.

    Verified to fail against the ``response_class=None`` regression this
    module was written for, and to pass once it was fixed.
    """
    captured = _capture_failing_route(monkeypatch)

    from app.main import app

    app.openapi_schema = None  # bypass the cached document

    try:
        schema = app.openapi()
    except AssertionError as exc:
        culprit = captured[0] if captured else "unknown (see traceback)"
        pytest.fail(
            f"OpenAPI generation failed: {exc}\n"
            f"Offending route: {culprit}\n"
            "A route declared a falsy response_class. Pass the response class "
            "the handler actually returns (e.g. response_class="
            "PlainTextResponse) rather than None."
        )

    assert schema["paths"], "OpenAPI generated no paths"
    assert "openapi" in schema

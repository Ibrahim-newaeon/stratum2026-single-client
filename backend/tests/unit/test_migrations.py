"""Migration-integrity guards (STRAT-SC-001 fix 12-1).

The audit flagged that no test asserted the Alembic chain stays single-headed
and linear, so model/migration drift (a branching or dangling revision) was only
ever caught indirectly. These cheap, DB-free checks fail fast in CI when a new
migration forks the history or leaves a second head — the usual cause of a
``alembic upgrade head`` that works locally but breaks a real deploy.
"""

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

# backend/tests/unit/test_migrations.py -> backend/
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _BACKEND_DIR / "alembic.ini"


@pytest.fixture(scope="module")
def script_dir() -> ScriptDirectory:
    cfg = Config(str(_ALEMBIC_INI))
    return ScriptDirectory.from_config(cfg)


def test_single_alembic_head(script_dir: ScriptDirectory) -> None:
    """Exactly one head — a second head means two migrations diverged."""
    heads = script_dir.get_heads()
    assert len(heads) == 1, (
        f"Expected exactly one Alembic head, found {len(heads)}: {heads}. "
        "Merge the branches with `alembic merge` or fix the down_revision."
    )


def test_migration_chain_is_linear(script_dir: ScriptDirectory) -> None:
    """Walking from the head reaches the base through a single unbroken chain."""
    (head,) = script_dir.get_heads()
    revisions = list(script_dir.walk_revisions(base="base", head=head))

    # No revision may have more than one parent (that would be a merge point).
    for rev in revisions:
        down = rev.down_revision
        assert not isinstance(down, (tuple, list)) or len(down) <= 1, (
            f"Revision {rev.revision} has multiple down_revisions {down} "
            "(a merge migration) — keep the single-client chain linear."
        )

    # Exactly one base (down_revision is None) and it terminates the chain.
    bases = [r.revision for r in revisions if r.down_revision is None]
    assert (
        len(bases) == 1
    ), f"Expected exactly one base revision (down_revision=None), found {bases}."

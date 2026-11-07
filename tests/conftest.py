import io
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.htree_builder import Session  # noqa: E402

TECH_LEF = ROOT / "tests" / "data" / "tech.lef"


@pytest.fixture
def session():
    return Session(out=io.StringIO())


@pytest.fixture
def tech_session(session):
    session.eval(f"read_tech -file {{{TECH_LEF}}}")
    session.out.seek(0)
    session.out.truncate()
    return session


@pytest.fixture
def write_lef(tmp_path):
    def _write(body: str, name: str = "t.lef") -> str:
        path = tmp_path / name
        path.write_text(body)
        return str(path)
    return _write

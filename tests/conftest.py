import io
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.htree_builder import Session  # noqa: E402

TECH_LEF = ROOT / "tests" / "data" / "tech.lef"


def pytest_configure(config):
    config.addinivalue_line("markers", "pin_vias: route_pin inserts its pin vias "
                            "(route_pin.INSERT_PIN_VIAS), as it does outside the tests")
    config.addinivalue_line("markers", "side_pins: route_pin gives a pin reached from the "
                            "side no strap (route_pin.SIDE_PINS), as outside the tests")


@pytest.fixture(autouse=True)
def no_pin_vias(request, monkeypatch):
    """route_pin's insert_vias after routing (route_pin.INSERT_PIN_VIAS) and
    its side pins (route_pin.SIDE_PINS) are off for the tests of the other
    commands, which count the shapes route_pin makes and the routes to its
    straps; tests/test_pin_vias.py and tests/test_side_pins.py turn them on
    (marks pin_vias, side_pins)."""
    from core.commands import route_pin
    if request.node.get_closest_marker("pin_vias") is None:
        monkeypatch.setattr(route_pin, "INSERT_PIN_VIAS", False)
    if request.node.get_closest_marker("side_pins") is None:
        monkeypatch.setattr(route_pin, "SIDE_PINS", False)


@pytest.fixture(autouse=True)
def log_dir(tmp_path, monkeypatch):
    """main() writes its log and cmd files here, not under the directory the
    tests run in."""
    from core import session_log
    monkeypatch.setattr(session_log, "DIR", str(tmp_path / "log"))
    return tmp_path / "log"


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

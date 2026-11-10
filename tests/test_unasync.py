import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "unasync.py"


def test_sync_resources_are_generated_from_async() -> None:
    spec = importlib.util.spec_from_file_location("unasync", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.TARGET.read_text() == module.generate(), (
        "_sync_resources.py is stale: run python scripts/unasync.py"
    )

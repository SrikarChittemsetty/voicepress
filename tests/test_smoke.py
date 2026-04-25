from pathlib import Path
import sys

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from new_project.cli import main


def test_cli_smoke(capsys):
    assert main(["--name", "Cursor"]) == 0
    out = capsys.readouterr().out
    assert "Hello, Cursor!" in out

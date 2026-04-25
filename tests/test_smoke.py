from new_project.cli import main


def test_cli_smoke(capsys):
    assert main(["--name", "Cursor"]) == 0
    out = capsys.readouterr().out
    assert "Hello, Cursor!" in out


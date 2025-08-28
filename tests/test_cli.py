import json, subprocess, sys


def test_cli_help():
    out = subprocess.check_output([sys.executable, "-m", "srpk", "-h"]).decode()
    assert "SRPK CLI" in out


def test_cli_analyze_json(tmp_path):
    out_json = tmp_path / "out.json"
    subprocess.check_call([sys.executable, "-m", "srpk", "analyze", ".", "-o", str(out_json)])
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data.get("ok") is True

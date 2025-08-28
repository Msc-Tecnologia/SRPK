import argparse
import json
import sys
from pathlib import Path

try:
    from srpk import analyze, __version__
except Exception:
    __version__ = "0.1.0"
    def analyze(path: str):
        return {"ok": True, "project": path}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="srpk", description="SRPK CLI")
    parser.add_argument("--version", action="version", version=f"srpk {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_analyze = sub.add_parser("analyze", help="Analiza un repo/proyecto")
    p_analyze.add_argument("path", nargs="?", default=".", help="Ruta del proyecto")
    p_analyze.add_argument("-o", "--out", help="Archivo JSON de salida")

    args = parser.parse_args(argv)
    if args.cmd == "analyze":
        res = analyze(args.path)
        out = json.dumps(res, ensure_ascii=False, indent=2)
        if args.out:
            Path(args.out).write_text(out, encoding="utf-8")
        else:
            print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

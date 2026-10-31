"""receipts <command>: fetch, check, probe, review, apply, test."""
import sys


def main(argv):
    cmd, args = (argv[0], argv[1:]) if argv else ("help", [])
    if cmd == "probe":
        from receipts import probes
        import json
        from pathlib import Path
        out = probes.ROOT / "out" / "receipts.json"
        receipts = json.loads(out.read_text()) if out.exists() and "--before" not in args else None
        print(probes.run(probes.load_entries(), receipts))
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])

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
    elif cmd == "check":
        from receipts import check
        ids = [a for a in args if not a.startswith("--")]
        if not ids and "--all" not in args:
            print("usage: receipts check [--all|<id>...] [--refresh]")
            return
        fresh, allr = check.run(ids or None, refresh="--refresh" in args)
        if ids:
            check.print_entry(fresh)
        print("this run:", check.summary(fresh))
        print("all receipts:", check.summary(allr), f"({len(allr)} claims) -> out/receipts.json")
    elif cmd == "apply":
        from receipts import apply
        if not args:
            print("usage: receipts apply out/decisions.json")
            return
        apply.run(args[0])
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])

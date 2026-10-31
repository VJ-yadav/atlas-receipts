"""receipts <command>: check, changes, probe, review, apply, test, goals."""
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
            print("usage: receipts check [--all|<id>...] [--refresh] [--model]")
            return
        fresh, allr = check.run(ids or None, refresh="--refresh" in args, use_model="--model" in args)
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
    elif cmd == "review":
        import json
        from receipts import review
        from receipts.probes import ROOT
        src = ROOT / "tests" / "fixtures" / "receipts.sample.json" if "--fixture" in args else ROOT / "out" / "receipts.json"
        out = review.build(json.loads(src.read_text()), ROOT / "out" / "review.html")
        print(f"wrote {out} ({src.name})")
    elif cmd == "changes":
        from receipts import changes
        changes.report()
    elif cmd == "goals":
        from receipts import goals
        sys.exit(1 if goals.run() else 0)
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])

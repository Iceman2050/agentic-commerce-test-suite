"""CLI: python -m commerce_suite check <store-dir> [--json]
        python -m commerce_suite check-all <fixtures-root> [--json]
        python -m commerce_suite verify <fixtures-root>

`verify` compares each store's actual findings against its expected.json
and exits non-zero on any mismatch.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .checker import check_store, format_report


def _stores(root: Path):
    return sorted(p for p in root.iterdir() if (p / "expected.json").exists())


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 2
    command, args = argv[0], argv[1:]
    as_json = "--json" in args
    args = [a for a in args if a != "--json"]

    if command == "check" and len(args) == 1:
        report = check_store(args[0])
        print(json.dumps(report, indent=2) if as_json else format_report(report))
        return 0

    if command == "check-all" and len(args) == 1:
        reports = [check_store(s) for s in _stores(Path(args[0]))]
        if as_json:
            print(json.dumps(reports, indent=2))
        else:
            print("\n\n".join(format_report(r) for r in reports))
        return 0

    if command == "verify" and len(args) == 1:
        failures = 0
        for store in _stores(Path(args[0])):
            expected = json.loads((store / "expected.json").read_text(encoding="utf-8"))
            report = check_store(store)
            want = sorted(
                (c["scope"], c["field"], c["surface_a"], c["value_a"],
                 c["surface_b"], c["value_b"])
                for c in expected["conflicts"]
            )
            got = sorted(
                (c["scope"], c["field"], c["surface_a"], c["value_a"],
                 c["surface_b"], c["value_b"])
                for c in report["conflicts"]
            )
            ok = want == got and report["verdict"] == expected["verdict"]
            print(f"{store.name}: {'OK' if ok else 'MISMATCH'} "
                  f"(expected {expected['verdict']}, got {report['verdict']}, "
                  f"{len(got)} conflict(s))")
            failures += 0 if ok else 1
        return 1 if failures else 0

    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

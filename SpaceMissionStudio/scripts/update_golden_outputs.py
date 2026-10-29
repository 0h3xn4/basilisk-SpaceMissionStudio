#
#  ISC License
#
#  Copyright (c) 2026, Autonomous Vehicle Systems Lab, University of Colorado at Boulder
#
#  Permission to use, copy, modify, and/or distribute this software for any
#  purpose with or without fee is hereby granted, provided that the above
#  copyright notice and this permission notice appear in all copies.
#
#  THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
#  WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
#  MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
#  ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
#  WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
#  ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
#  OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
#
"""Compare or rewrite the regression baseline in ``tests/golden/``
(``tests/golden_capture.py``).

    python scripts/update_golden_outputs.py              # compare every template, write nothing
    python scripts/update_golden_outputs.py --write      # rewrite every fingerprint
    python scripts/update_golden_outputs.py 01_two_body  # only templates whose name starts so

Rewrite only for a change that is meant: each number that changes needs an
entry in ``docs/changes.md`` with its before and after values. The comparison
printed before writing lists them.
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import golden_capture  # noqa: E402 -- after the path above


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("only", nargs="*", help="template name prefixes (default: all)")
    parser.add_argument("--write", action="store_true", help="rewrite the stored fingerprints")
    args = parser.parse_args(argv)
    paths = [p for p in golden_capture.template_paths() if not args.only or any(p.stem.startswith(o) for o in args.only)]
    changed = 0
    for path in paths:
        started = time.perf_counter()
        actual = golden_capture.capture(path)
        stored = golden_capture.GOLDEN / f"{path.stem}.json"
        problems = (golden_capture.compare(json.loads(stored.read_text(encoding="utf-8")), actual)
                    if stored.exists() else ["no stored fingerprint"])
        print(f"{path.stem}: {len(problems)} difference(s), {time.perf_counter() - started:.1f} s")
        for problem in problems[:20]:
            print(f"    {problem}")
        if len(problems) > 20:
            print(f"    ... and {len(problems) - 20} more")
        changed += bool(problems)
        if args.write:
            golden_capture.GOLDEN.mkdir(exist_ok=True)
            stored.write_text(json.dumps(actual, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{changed} of {len(paths)} template(s) differ" + (" (rewritten)" if args.write else ""))
    return 1 if changed and not args.write else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""//// Neoffice — added file (no upstream equivalent).

Inventory of everything this fork changes, and a guard that fails when a piece
of it disappears.

Why this exists
---------------
On 2026-08-09 we merged frappe/wiki v3.0.0 (493 commits). Several Neoffice
behaviours were gone afterwards and nobody noticed until a human browsed the
site days later:

  * the guard that hid the space-settings gear from anonymous visitors — it sat
    in SpaceDetails.vue, in the header region upstream rewrote into
    SpaceTreePanel.vue, so it left with the container. No conflict was raised;
  * the space switcher, same file, same reason;
  * our reader CSS, which an EARLIER sync had already killed months before by
    deleting the SCSS bundle that imported it. The partial went on existing
    while nothing compiled it. That one was invisible for months.

None of those changes were marked `//// Neoffice` at the time — the marking
rule landed with the merge — so after the merge there was no way to ask "what
did we have?" other than reading a year of diffs.

Marking alone is not enough either: a marker only proves intent where the code
still is. What closes the loop is a checked-in list of those markers, compared
on every push. If a marked block vanishes, this fails and names it.

What it does NOT catch: holes upstream OPENS in code we never touched (the
unfiltered switcher query, the Edit button offered to guests). Nothing static
can. Those belong in tests — see test_wiki_document.py — and in the guest pass
of the three-identity check after every merge.

Usage
-----
    python3 scripts/neoffice-divergence.py            # check (CI)
    python3 scripts/neoffice-divergence.py --update   # re-bless after an
                                                      # intentional removal
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BASELINE = REPO / "neoffice-divergence.json"

MARKER = re.compile(r"////\s*(Neoffice|Neoservice)\b[ \t—-]*(?P<text>.*)$")

# Built output and vendored trees: the markers in them are copies of the source
# markers, so counting them would double every entry and churn on every build.
EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    "dist",
    "frontend/node_modules",
    "wiki/public/frontend",
    "wiki/public/js",
    "wiki/public/css",
}
EXCLUDED_SUFFIXES = {".po", ".pot", ".mo", ".map", ".lock", ".json"}


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    files = []
    for rel in out:
        if any(rel == d or rel.startswith(d + "/") for d in EXCLUDED_DIRS):
            continue
        path = REPO / rel
        if path.suffix in EXCLUDED_SUFFIXES or not path.is_file():
            continue
        files.append(path)
    return files


def scan() -> dict[str, list[str]]:
    """Map each file to the first line of every marker block it holds.

    Consecutive marker lines are one block: our comments run several lines and
    only the first carries the claim. Reflowing a block must not look like a
    deletion, so only that first line is recorded.
    """
    inventory: dict[str, list[str]] = {}

    for path in tracked_files():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue

        blocks: list[str] = []
        in_block = False
        for line in lines:
            match = MARKER.search(line)
            if not match:
                in_block = False
                continue
            if not in_block:
                text = " ".join(match.group("text").split())
                blocks.append(text or "(unlabelled)")
                in_block = True

        if blocks:
            inventory[str(path.relative_to(REPO))] = blocks

    return inventory


def load_baseline() -> dict[str, list[str]]:
    if not BASELINE.exists():
        return {}
    return json.loads(BASELINE.read_text(encoding="utf-8"))["files"]


def write_baseline(inventory: dict[str, list[str]]) -> None:
    total = sum(len(v) for v in inventory.values())
    BASELINE.write_text(
        json.dumps(
            {
                "_comment": (
                    "Inventory of this fork's divergence from frappe/wiki. "
                    "Regenerate with: python3 scripts/neoffice-divergence.py --update. "
                    "A dropped entry is a Neoffice change that an upstream merge ate."
                ),
                "marked_blocks": total,
                "files": {k: inventory[k] for k in sorted(inventory)},
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Baseline written: {total} marked blocks across {len(inventory)} files.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="rewrite the baseline")
    args = parser.parse_args()

    inventory = scan()

    if args.update:
        write_baseline(inventory)
        return 0

    baseline = load_baseline()
    if not baseline:
        print("No baseline yet — run with --update to create one.", file=sys.stderr)
        return 1

    lost_files = sorted(set(baseline) - set(inventory))
    lost_blocks: list[tuple[str, str]] = []
    for path, blocks in baseline.items():
        if path in lost_files:
            continue
        current = inventory.get(path, [])
        for block in blocks:
            if block not in current:
                lost_blocks.append((path, block))

    if not lost_files and not lost_blocks:
        total = sum(len(v) for v in inventory.values())
        gained = total - sum(len(v) for v in baseline.values())
        note = f" (+{gained} new)" if gained > 0 else ""
        print(f"OK — all {sum(len(v) for v in baseline.values())} marked blocks still present{note}.")
        return 0

    print("Neoffice changes have gone missing since the last blessed baseline.\n")
    for path in lost_files:
        print(f"  FILE GONE   {path}")
        for block in baseline[path]:
            print(f"              - {block}")
    for path, block in lost_blocks:
        print(f"  BLOCK GONE  {path}")
        print(f"              - {block}")
    print(
        "\nIf an upstream merge ate these, restore them. If you removed them on"
        "\npurpose, re-bless with: python3 scripts/neoffice-divergence.py --update"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

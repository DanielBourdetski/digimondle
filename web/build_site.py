"""Inline the game data into web/template.html and write a self-contained index.html.

One file, no fetch() at load, so it works from file:// by double-clicking as well
as from GitHub Pages. Card images are still pulled from the network at play time —
that is deliberate, so a new set does not require rebuilding the page.
"""

import io as _io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = os.path.join(ROOT, "data", "build", "game")
TEMPLATE = os.path.join(HERE, "template.html")
OUT = os.path.join(ROOT, "index.html")

MARKER = "/* DATA */"


BUILD = os.path.join(ROOT, "data", "build")


def read(name, folder=None):
    with _io.open(os.path.join(folder or GAME, name), encoding="utf-8") as fh:
        return fh.read()


def main():
    with _io.open(TEMPLATE, encoding="utf-8") as fh:
        html = fh.read()

    if MARKER not in html:
        raise SystemExit(f"template is missing the {MARKER} marker")

    blocks = [
        ("RAW_CARDS", read("cards.min.json")),
        ("SCHEDULE", read("schedule.json")),
        ("EFFECTS", read("effects.json")),
        ("META", read("meta.json")),
        # English release month per set — what the Set column's arrow points with
        ("SET_DATES", read("set_dates.json", BUILD)),
    ]
    data = "\n".join(f"const {name} = {body};" for name, body in blocks)

    html = html.replace(MARKER, data)

    # </script> anywhere inside the JSON would close the block early
    if "</script>" in data:
        raise SystemExit("data contains a literal </script>; escape it before shipping")

    with _io.open(OUT, "w", encoding="utf-8") as fh:
        fh.write(html)

    size = os.path.getsize(OUT) / 1e6
    print(f"index.html  {size:.2f} MB")
    for name, body in blocks:
        print(f"  {name:10} {len(body)/1024:7.0f} KB")


if __name__ == "__main__":
    main()

"""Pull English release months for every card set from the DigimonCardGame wiki.

The card data has no usable release date — digimoncard.io's `date_added` is when
the row was imported, so every set older than the import is tied at 2025-11-25.
Without real dates the Set column cannot point anywhere.

The wiki's set-list pages group releases under `===Month, Year===` headings
inside a `|-|Worldwide Release=` tabber, which is exactly the ordering needed.
Only that tab is read; the Japanese tab lists the same sets months earlier.

Output: data/build/set_dates.json  {"BT1": "2020-11", ...}
"""

import io as _io
import json
import os
import re
import sys
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "data", "build")

API = "https://digimoncardgame.fandom.com/api.php"
PAGES = ["Booster Sets", "Starter Decks", "Promotional Cards"]

# not real sets — "P" is every promo ever and "LM" bundles LM-01..LM-08, which
# span years, so neither can carry one release date
UNDATED_BY_DESIGN = {"P", "LM"}
UA = "digimondle-setdates/1.0 (personal hobby project)"

MONTHS = {m: i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June",
     "July", "August", "September", "October", "November", "December"])}


def wikitext(page):
    url = f"{API}?action=parse&page={urllib.parse.quote(page)}&prop=wikitext&format=json"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if "parse" not in data:
        return ""
    return data["parse"]["wikitext"]["*"]


ENGLISH_TABS = ("Worldwide Release", "English Release")


def english_sections(text):
    """The English-language tabs only.

    The page is a five-tab tabber — Worldwide, English, Japanese, Chinese,
    Korean — and the Japanese tab lists the same sets months earlier, so mixing
    them in would scramble the order outright. Two tabs are needed rather than
    one: Bandai only unified releases in April 2025, so "Worldwide" covers
    2025-04 onward and everything older sits under "English".
    """
    out = []
    for tab in ENGLISH_TABS:
        start = text.find(f"|-|{tab}=")
        if start == -1:
            continue
        rest = text[start + len(tab) + 4:]
        end = rest.find("|-|")
        out.append(rest[:end] if end != -1 else rest)
    return "\n".join(out) if out else text


# The English releases bundled several numbered sets into one product, and the
# wiki lists those under a version code rather than a set code. Reading "BT2.0"
# as "BT2" is not just a miss, it is actively wrong: it dated BT-02 to November
# 2024 when BT-02 actually shipped in the Ver.1.0 bundle in January 2021.
# Contents confirmed against printedIn in our own card data.
BUNDLES = {
    "BT1.0": ["BT1", "BT2", "BT3"],    # BT01-03: Release Special Booster Ver.1.0
    "BT1.5": ["BT1", "BT2", "BT3"],    # BT01-03: Release Special Booster Ver.1.5
    "BT2.0": ["BT18", "BT19"],         # BT18-19: Special Booster Ver.2.0
    "BT2.5": ["BT19", "BT20"],         # BT19-20: Special Booster Ver.2.5
}


def parse(text):
    """{set code: 'YYYY-MM'} from the ===Month, Year=== headings."""
    out = {}
    current = None

    def record(code, when):
        # a set can ship in more than one bundle (BT-19 is in both Ver.2.0 and
        # Ver.2.5); its release date is the first time it was buyable
        if code not in out or when < out[code]:
            out[code] = when

    for line in english_sections(text).splitlines():
        heading = re.match(r"^===\s*([A-Za-z]+),?\s*(\d{4})\s*===", line.strip())
        if heading:
            month, year = heading.group(1), int(heading.group(2))
            current = f"{year:04d}-{MONTHS[month]:02d}" if month in MONTHS else None
            continue
        if not current:
            continue
        for raw in re.findall(r"setLinks\|([A-Za-z0-9.\-]+)", line):
            if raw in BUNDLES:
                for code in BUNDLES[raw]:
                    record(code, current)
                continue
            if "." in raw:
                continue          # an unknown bundle — better skipped than guessed
            m = re.match(r"^([A-Za-z]{1,3})-?(\d{1,2})$", raw)
            if m:
                record(f"{m.group(1).upper()}{int(m.group(2))}", current)
    return out


def main():
    dates = {}
    for page in PAGES:
        try:
            found = parse(wikitext(page))
        except Exception as exc:
            print(f"  FAIL {page}: {exc}")
            continue
        new = {k: v for k, v in found.items() if k not in dates or v < dates[k]}
        dates.update(new)
        print(f"  {page:20} {len(found):3} sets ({len(new)} new)")

    os.makedirs(BUILD, exist_ok=True)
    path = os.path.join(BUILD, "set_dates.json")
    with _io.open(path, "w", encoding="utf-8") as fh:
        json.dump(dict(sorted(dates.items(), key=lambda kv: kv[1])), fh,
                  indent=1, ensure_ascii=False)

    print(f"\nwrote {path} ({len(dates)} sets)")

    # report against the sets the game actually uses
    cards_path = os.path.join(BUILD, "cards.json")
    if os.path.exists(cards_path):
        with _io.open(cards_path, encoding="utf-8") as fh:
            used = {c["setCode"] for c in json.load(fh) if c["inPool"]}
        # P and LM are not single sets: each holds packs spanning years
        missing = sorted(used - set(dates) - UNDATED_BY_DESIGN)
        print(f"sets in the pool: {len(used)}   dated: {len(used & set(dates))}   "
              f"undated: {len(missing)}")
        if missing:
            print("  undated:", ", ".join(missing))

    print("\nrelease order:")
    for code, when in sorted(dates.items(), key=lambda kv: (kv[1], kv[0])):
        print(f"  {when}  {code}")


if __name__ == "__main__":
    main()

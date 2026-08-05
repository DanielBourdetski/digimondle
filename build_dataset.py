"""Merge + normalise the raw sources into one clean card list for the game.

TakaOtaku is the base (one row per card number, multilingual, ban list, alt-art
list). digimoncard.io fills in release date, set membership and tcgplayer ids.

Output: data/build/cards.json  +  data/build/stats.json
"""

import io as _io
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "raw")
BUILD = os.path.join(HERE, "data", "build")

# Values that mean "this field does not apply to this card"
EMPTY = {"-", "", "NO DATA", None, "Unknown"}

# Sets that are English-only reprints/promos still worth keeping
SET_PREFIX_NAMES = {
    "BT": "Booster",
    "EX": "Extra Booster",
    "ST": "Starter Deck",
    "P": "Promo",
    "LM": "Limited",
    "RB": "Reboot Booster",
    "AD": "Advance Deck",
}


def load(path):
    with _io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


def clean(value):
    """Normalise a scalar field; '-' and friends become None."""
    if isinstance(value, str):
        value = value.strip()
    return None if value in EMPTY else value


def as_int(value):
    value = clean(value)
    if value is None:
        return None
    m = re.search(r"-?\d+", str(value))
    return int(m.group()) if m else None


def split_list(value, sep="/"):
    """'Enhancement/Twilight' -> ['Enhancement', 'Twilight']"""
    value = clean(value)
    if not value:
        return []
    return [p.strip() for p in value.split(sep) if p.strip() and p.strip() not in EMPTY]


def norm_key(card_number):
    """Match ids across sources: RB1-10 and RB1-010 are the same card."""
    m = re.match(r"^([A-Za-z]+)(\d+)-(\d+)([A-Za-z0-9_-]*)$", card_number.strip())
    if not m:
        return card_number.strip().upper()
    prefix, set_no, card_no, suffix = m.groups()
    return f"{prefix.upper()}{int(set_no)}-{int(card_no)}{suffix.upper()}"


def set_prefix(card_number):
    m = re.match(r"^([A-Za-z]+)", card_number)
    return m.group(1).upper() if m else "?"


def set_code(card_number):
    """'BT26-001' -> 'BT26'"""
    return card_number.split("-")[0].upper()


# --------------------------------------------------------------------------
# load sources
# --------------------------------------------------------------------------
tk = load(os.path.join(RAW, "takaotaku_cards.json"))
io_rows = load(os.path.join(RAW, "digimoncard_io.json"))

# digimoncard.io has one row per printing; collapse to one record per card
io_by_key = defaultdict(list)
for row in io_rows:
    if row.get("id"):
        io_by_key[norm_key(row["id"])].append(row)

# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------
cards = []
matched = 0

for src in tk:
    number = src["cardNumber"].strip()
    key = norm_key(number)
    io_rows_for_card = io_by_key.get(key, [])
    if io_rows_for_card:
        matched += 1
    primary = io_rows_for_card[0] if io_rows_for_card else {}

    names = src.get("name") or {}
    colors = split_list(src.get("color"))
    types = split_list(src.get("type"))
    card_types = split_list(src.get("cardType"))

    # every set this card was ever printed in, across both sources
    sets = set()
    for row in io_rows_for_card:
        for s in row.get("set_name") or []:
            sets.add(s)

    restrictions = src.get("restrictions") or {}
    status_en = clean(restrictions.get("english")) or "Unrestricted"

    card = {
        "id": number,
        "name": clean(names.get("english")) or clean(src.get("name")) or number,
        "names": {k: v for k, v in names.items() if clean(v)},

        # --- primary guessable attributes ---
        "cardType": card_types[0] if card_types else None,
        "cardTypes": card_types,
        "colors": colors,
        "level": as_int(src.get("cardLv")),
        "playCost": as_int(src.get("playCost")),
        "dp": as_int(src.get("dp")),
        "form": clean(src.get("form")),
        "attribute": clean(src.get("attribute")),
        "types": types,
        "rarity": clean(src.get("rarity")),
        "illustrator": clean(src.get("illustrator")) or clean(primary.get("artist")),

        # --- set / release info ---
        "setCode": set_code(number),
        "setPrefix": set_prefix(number),
        "setCategory": SET_PREFIX_NAMES.get(set_prefix(number), "Other"),
        "blocks": [b for b in (src.get("block") or []) if b],
        "printedIn": sorted(sets),
        "dateAdded": clean(primary.get("date_added")),

        # --- rules text (for hint modes) ---
        "effect": clean(src.get("effect")),
        "inheritedEffect": clean(src.get("digivolveEffect")),
        "securityEffect": clean(src.get("securityEffect")),
        "digivolveCondition": src.get("digivolveCondition") or [],
        "digiXros": clean(src.get("digiXros")),
        "dnaDigivolve": clean(src.get("dnaDigivolve")),
        "aceEffect": clean(src.get("aceEffect")),
        "linkRequirement": clean(src.get("linkRequirement")),
        "linkDP": as_int(src.get("linkDP")),
        "rule": clean(src.get("rule")),

        # --- status ---
        "restriction": status_en,
        "released": status_en != "Not released",
        "altArtCount": len(src.get("AAs") or []),

        # --- images (loaded at runtime, never mirrored) ---
        # digimoncard.app is primary: clean scans at 430x601. digimoncard.io
        # stamps a giant SAMPLE watermark across some cards (BT24-082 among
        # them, which the schedule uses on day 6) and only serves 300x419.
        # It is still needed as fallback because digimoncard.app has not picked
        # up BT-26 yet — and it answers missing cards with its SPA shell as
        # text/html rather than a 404, so the <img> onerror handler is what
        # actually switches hosts.
        # Neither host has to send CORS headers: the art reveal uses CSS
        # transform + filter, never canvas pixel reads, so nothing is tainted.
        "image": {
            "primary": f"https://digimoncard.app/{src.get('cardImage')}" if src.get("cardImage") else None,
            "fallback": f"https://images.digimoncard.io/images/cards/{number}.jpg",
            "official": f"https://world.digimoncard.com/images/cardlist/card/{number}.png",
        },

        # --- extras ---
        "tcgplayerId": primary.get("tcgplayer_id"),
    }

    # a card is eligible for the daily puzzle if it's a real, released card
    card["inPool"] = bool(
        card["released"]
        and card["cardType"]
        and card["name"]
    )

    cards.append(card)

cards.sort(key=lambda c: (c["setPrefix"], c["id"]))

# --------------------------------------------------------------------------
# stats
# --------------------------------------------------------------------------
pool = [c for c in cards if c["inPool"]]
digimon = [c for c in pool if c["cardType"] == "Digimon"]


def dist(items, key):
    counter = Counter()
    for c in items:
        val = key(c)
        if isinstance(val, list):
            for v in val:
                counter[v] += 1
        else:
            counter[val] += 1
    return dict(counter.most_common())


stats = {
    "totalCards": len(cards),
    "matchedWithIo": matched,
    "inPool": len(pool),
    "digimonInPool": len(digimon),
    "notReleased": sum(1 for c in cards if not c["released"]),
    "missingImagePrimary": sum(1 for c in cards if not c["image"]["primary"]),
    "distributions": {
        "cardType": dist(pool, lambda c: c["cardType"]),
        "colorCount": dist(pool, lambda c: len(c["colors"])),
        "color": dist(pool, lambda c: c["colors"]),
        "level": dist(digimon, lambda c: c["level"]),
        "form": dist(digimon, lambda c: c["form"]),
        "attribute": dist(digimon, lambda c: c["attribute"]),
        "rarity": dist(pool, lambda c: c["rarity"]),
        "setCategory": dist(pool, lambda c: c["setCategory"]),
        "restriction": dist(cards, lambda c: c["restriction"]),
        "playCost": dist(pool, lambda c: c["playCost"]),
        "dp": dist(digimon, lambda c: c["dp"]),
    },
    "topTypes": dict(Counter(t for c in pool for t in c["types"]).most_common(40)),
    "topIllustrators": dict(Counter(c["illustrator"] for c in pool if c["illustrator"]).most_common(25)),
}

os.makedirs(BUILD, exist_ok=True)
with _io.open(os.path.join(BUILD, "cards.json"), "w", encoding="utf-8") as fh:
    json.dump(cards, fh, ensure_ascii=False, indent=None, separators=(",", ":"))
with _io.open(os.path.join(BUILD, "stats.json"), "w", encoding="utf-8") as fh:
    json.dump(stats, fh, ensure_ascii=False, indent=2)

size = os.path.getsize(os.path.join(BUILD, "cards.json")) / 1e6
print(f"cards.json  {len(cards)} cards, {size:.2f} MB")
print(f"  matched against digimoncard.io : {matched}")
print(f"  eligible for daily pool        : {len(pool)}  (Digimon only: {len(digimon)})")
print(f"  not released in English        : {stats['notReleased']}")
print(f"  no primary image path          : {stats['missingImagePrimary']}")

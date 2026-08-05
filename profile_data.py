"""Profile the raw data so we can decide which fields make good guessing attributes."""

import io
import json
import os
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "raw")


def load(name):
    return json.load(io.open(os.path.join(RAW, name), encoding="utf-8"))


def show(title, counter, limit=20):
    total = sum(counter.values())
    print(f"\n-- {title}  ({len(counter)} distinct, {total} values)")
    for val, n in counter.most_common(limit):
        print(f"     {str(val)[:48]:50} {n:5}")
    if len(counter) > limit:
        print(f"     ... +{len(counter)-limit} more")


tk = load("takaotaku_cards.json")
io_ = load("digimoncard_io.json")

print("=" * 70)
print(f"TakaOtaku: {len(tk)} entries, {len({c['cardNumber'] for c in tk})} unique cardNumbers")
print(f"digimoncard.io: {len(io_)} rows, {len({c['id'] for c in io_})} unique ids")

# --- how the two sources overlap ---
tk_ids = {c["cardNumber"] for c in tk}
io_ids = {c["id"] for c in io_}
print(f"\nin both: {len(tk_ids & io_ids)} | only TakaOtaku: {len(tk_ids - io_ids)} | only io: {len(io_ids - tk_ids)}")
print("  sample only-TakaOtaku:", sorted(tk_ids - io_ids)[:8])
print("  sample only-io      :", sorted(io_ids - tk_ids)[:8])

# --- what makes an entry a duplicate ---
print("\n" + "=" * 70)
print("TakaOtaku 'version' field (alt arts vs normal):")
show("version", Counter(c["version"] for c in tk))

dupes = Counter(c["cardNumber"] for c in tk)
print(f"\ncardNumbers with >1 entry: {sum(1 for v in dupes.values() if v > 1)}")
print("  worst:", dupes.most_common(3))

# --- candidate guessing attributes ---
print("\n" + "=" * 70)
print("CANDIDATE GUESS ATTRIBUTES (TakaOtaku, all entries)")
for field in ["color", "cardType", "cardLv", "form", "attribute", "rarity", "playCost", "dp"]:
    show(field, Counter(c.get(field) for c in tk))

# type is slash-separated ("Enhancement/Twilight")
types = Counter()
for c in tk:
    for t in (c.get("type") or "").split("/"):
        t = t.strip()
        if t and t != "-":
            types[t] += 1
show("type (split on /)", types, 25)

show("illustrator", Counter(c.get("illustrator") for c in tk), 12)

blocks = Counter()
for c in tk:
    for b in c.get("block") or []:
        blocks[b] += 1
show("block", blocks)

# --- set prefixes ---
prefix = Counter()
for c in tk:
    m = re.match(r"([A-Z]+)", c["cardNumber"])
    if m:
        prefix[m.group(1)] += 1
show("set prefix", prefix, 30)

# --- ban list ---
restr = Counter()
for c in tk:
    r = (c.get("restrictions") or {}).get("english")
    restr[r] += 1
show("restrictions.english", restr)

# --- io extras we might want ---
print("\n" + "=" * 70)
print("digimoncard.io extras")
print("  keys:", list(io_[0].keys()))
print("  rows per id (alt printings):", Counter(Counter(c['id'] for c in io_).values()).most_common(5))
show("io rarity", Counter(c.get("rarity") for c in io_))
print("\n  newest date_added values:")
for d in sorted({c.get("date_added") or "" for c in io_})[-5:]:
    print("   ", d)

# --- multilingual name coverage ---
print("\n" + "=" * 70)
langs = Counter()
for c in tk:
    for lang, val in (c.get("name") or {}).items():
        if val and val != "-":
            langs[lang] += 1
show("name languages present", langs)

# --- how many are "real" playable unique cards ---
normal = [c for c in tk if c.get("version") == "Normal"]
print(f"\nversion == 'Normal': {len(normal)} entries, {len({c['cardNumber'] for c in normal})} unique numbers")

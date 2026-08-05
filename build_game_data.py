"""Turn cards.json into what the browser actually downloads, plus the daily schedules.

Outputs (data/build/game/):
  cards.min.json   slim card rows for the grid + autocomplete
  effects.json     rules text with the card's own name masked, for Effect mode
  schedule.json    a fixed, pre-rolled answer per day per mode
  meta.json        counts and build info
"""

import io as _io
import json
import os
import random
import re
import sys
from collections import Counter
from datetime import date, timedelta

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "data", "build")
GAME = os.path.join(BUILD, "game")

START_DATE = date(2026, 8, 5)
DAYS = 365
SCHEDULE_SEED = 20260805

# curation: how far apart repeats have to be
MIN_GAP_NAME = 60   # days before the same Digimon name can come round again
MIN_GAP_SET = 5     # days before the same set can come round again

MASK = "█████"


def load_cards():
    with _io.open(os.path.join(BUILD, "cards.json"), encoding="utf-8") as fh:
        return json.load(fh)


def clean_image_hosts():
    """{card_id: 'io'} for cards whose digimoncard.app scan carries a SAMPLE
    watermark. Written by detect_sample.py; absent is fine, the default host
    just gets used for everything."""
    path = os.path.join(BUILD, "image_host.json")
    if not os.path.exists(path):
        return {}
    with _io.open(path, encoding="utf-8") as fh:
        hosts = json.load(fh)
    # only the cards that need the non-default host are worth shipping
    return {cid: h for cid, h in hosts.items() if h == "io"}


def fetched_at():
    path = os.path.join(HERE, "data", "raw", "fetched_at.txt")
    if not os.path.exists(path):
        return None
    with _io.open(path, encoding="utf-8") as fh:
        return fh.read().strip()


# ---------------------------------------------------------------------------
# slim export
# ---------------------------------------------------------------------------
def slim(card, io_hosts=()):
    """Only what the grid and the autocomplete need.

    Image URLs are left out on purpose: they are a pure function of the id
    (https://images.digimoncard.io/images/cards/{id}.jpg), so storing them
    would nearly double the payload for no information.
    """
    return {
        "id": card["id"],
        "n": card["name"],
        "t": card["cardType"],
        "c": card["colors"],
        "lv": card["level"],
        "pc": card["playCost"],
        "dp": card["dp"],
        "f": card["form"],
        "a": card["attribute"],
        "ty": card["types"],
        "s": card["setCode"],
        # LM cards carry whatever rarity their pack happened to print (C/U/R/SR/
        # SEC/P), but the whole LM line is a promo channel, so the game treats
        # them as promos and the rarity ladder puts them with P.
        "r": "P" if card["setCode"] == "LM" else card["rarity"],
        "i": card["illustrator"],
        # ACE is printed on the card but never appears in its name, and players
        # do say "MetalGreymon ACE" — so it ships as an extra search term.
        # 79 cards, cheap enough to be worth it.
        **({"ace": 1} if card["aceEffect"] else {}),
        # only set when the default host's scan is watermarked and the other
        # one's is clean, so the flag costs nothing on the ~94% that are fine
        **({"h": "io"} if card["id"] in io_hosts else {}),
    }


SLIM_KEYS = {
    "id": "id", "n": "name", "t": "cardType", "c": "colors", "lv": "level",
    "pc": "playCost", "dp": "dp", "f": "form", "a": "attribute",
    "ty": "types", "s": "setCode", "r": "rarity", "i": "illustrator",
    "ace": "isAce", "h": "imageHost",
}


# ---------------------------------------------------------------------------
# effect text masking
# ---------------------------------------------------------------------------
def name_variants(name):
    """'SkullKnightmon: Mighty Axe Mode' -> both the full name and 'SkullKnightmon'."""
    variants = {name}
    if ":" in name:
        variants.add(name.split(":")[0].strip())
    # 'Omnimon X Antibody' -> 'Omnimon'
    variants.add(re.sub(r"\s+(X Antibody|ACE|Alt\.?)$", "", name).strip())
    return sorted({v for v in variants if len(v) > 2}, key=len, reverse=True)


def _bounded(variant):
    """Match the name only as a whole word.

    Without this, masking 'Greymon' also eats the 'Greymon' inside
    'MetalGreymon', turning a reference to a *different* card into
    '[Metal█████]' — which both corrupts the text and half-leaks the answer.
    Plain \\b will not do, because names like 'Dynasmon (X Antibody)' end in a
    non-word character, so the boundary is only asserted where it makes sense.
    """
    pattern = re.escape(variant)
    if variant[0].isalnum():
        pattern = r"(?<![A-Za-z0-9])" + pattern
    if variant[-1].isalnum():
        pattern = pattern + r"(?![A-Za-z0-9])"
    return pattern


def mask_effect(text, name):
    if not text:
        return None
    for variant in name_variants(name):
        # single letters and other very short names (the Tamer literally called
        # 'K') are left alone; masking them would shred the whole sentence
        if len(variant) < 4:
            continue
        text = re.sub(_bounded(variant), MASK, text, flags=re.IGNORECASE)
    return text


# ---------------------------------------------------------------------------
# notability: bias the daily pick towards cards people have actually seen
# ---------------------------------------------------------------------------
RARITY_WEIGHT = {"SEC": 3.0, "UR": 3.0, "SR": 2.0, "R": 1.4, "P": 1.2, "U": 1.0, "C": 0.9}


def notability(card):
    """Not a popularity metric, just a proxy: cards that were reprinted a lot or
    got alternate art tend to be the ones players recognise."""
    score = 1.0
    score += 0.6 * min(len(card["printedIn"]), 6)
    score += 0.5 * min(card["altArtCount"], 5)
    score *= RARITY_WEIGHT.get(card["rarity"], 1.0)
    if card["restriction"] in ("Banned", "Restricted to 1"):
        score *= 1.5  # meta-relevant cards
    return score


# ---------------------------------------------------------------------------
# schedule
# ---------------------------------------------------------------------------
def previous_schedule():
    """The schedule from the last build, if there is one."""
    path = os.path.join(GAME, "schedule.json")
    if not os.path.exists(path):
        return None
    try:
        with _io.open(path, encoding="utf-8") as fh:
            old = json.load(fh)
    except Exception:
        return None
    return old if old.get("startDate") == START_DATE.isoformat() else None


def days_elapsed():
    """How many schedule days are already spoken for.

    Today counts: its answer is live and someone may already have played it, so
    the range that gets frozen is inclusive of the current day.
    """
    return max(0, (date.today() - START_DATE).days + 1)


def build_schedule(pool, days, seed, label, keep=()):
    """Weighted pick per day.

    Hard rule: a card is never used twice in the same schedule — picks are drawn
    without replacement. Soft rules: keep the same Digimon name and the same set
    a few weeks apart. The soft rules get relaxed rather than deadlock the slot,
    and every relaxation is counted so it shows up in the build output.
    """
    rng = random.Random(seed)

    # Days that have already happened are frozen. Adding cards to the pool
    # changes every draw that follows, so without this a rebuild after a new set
    # would silently rewrite answers people have already played — and the
    # October fix that added 238 cards would have reshuffled the whole year.
    by_id = {c["id"]: c for c in pool}
    frozen = [cid for cid in keep if cid in by_id][:days]
    used = set(frozen)

    remaining = [c for c in pool if c["id"] not in used]
    weights = [notability(c) for c in remaining]

    picked = list(frozen)
    last_name = {}
    last_set = {}
    relaxed = 0
    for day, cid in enumerate(frozen):
        last_name[by_id[cid]["name"]] = day
        last_set[by_id[cid]["setCode"]] = day

    for day in range(len(frozen), days):
        choice = choice_idx = None
        for attempt in range(600):
            idx = rng.choices(range(len(remaining)), weights=weights, k=1)[0]
            candidate = remaining[idx]
            strict = attempt < 400
            gap_name = MIN_GAP_NAME if strict else 14
            gap_set = MIN_GAP_SET if strict else 1
            if day - last_name.get(candidate["name"], -9999) < gap_name:
                continue
            if day - last_set.get(candidate["setCode"], -9999) < gap_set:
                continue
            if not strict:
                relaxed += 1
            choice, choice_idx = candidate, idx
            break
        if choice is None:
            choice_idx = rng.randrange(len(remaining))
            choice = remaining[choice_idx]
            relaxed += 1

        # drawn without replacement, so it can never come round again
        remaining.pop(choice_idx)
        weights.pop(choice_idx)

        last_name[choice["name"]] = day
        last_set[choice["setCode"]] = day
        picked.append(choice["id"])

    note = f", {relaxed} slots needed relaxed spacing" if relaxed else ""
    held = f", {len(frozen)} already-played days kept" if frozen else ""
    print(f"  {label:8} {len(picked)} days, {len(set(picked))} distinct cards{note}{held}")
    return picked


def main():
    os.makedirs(GAME, exist_ok=True)
    cards = load_cards()
    pool = [c for c in cards if c["inPool"]]

    # --- slim cards ---
    io_hosts = clean_image_hosts()
    slim_cards = [slim(c, io_hosts) for c in pool]
    path = os.path.join(GAME, "cards.min.json")
    with _io.open(path, "w", encoding="utf-8") as fh:
        json.dump({"keys": SLIM_KEYS, "cards": slim_cards}, fh,
                  ensure_ascii=False, separators=(",", ":"))
    print(f"cards.min.json  {len(slim_cards)} cards, {os.path.getsize(path)/1024:.0f} KB"
          f"  ({len(io_hosts)} pinned to the digimoncard.io scan)")

    # --- effects ---
    effects = {}
    for c in pool:
        e = {
            "e": mask_effect(c["effect"], c["name"]),
            "i": mask_effect(c["inheritedEffect"], c["name"]),
            "s": mask_effect(c["securityEffect"], c["name"]),
        }
        e = {k: v for k, v in e.items() if v}
        if e:
            effects[c["id"]] = e
    path = os.path.join(GAME, "effects.json")
    with _io.open(path, "w", encoding="utf-8") as fh:
        json.dump(effects, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"effects.json    {len(effects)} cards, {os.path.getsize(path)/1024:.0f} KB")

    # --- schedules ---
    print("schedules:")
    classic_pool = pool
    art_pool = pool
    effect_pool = [c for c in pool if c["id"] in effects]

    old = previous_schedule()
    played = days_elapsed()
    keep = {mode: (old["modes"].get(mode, [])[:played] if old else [])
            for mode in ("classic", "art", "effect")}
    if played:
        print(f"  ({played} day(s) already played — those answers are held fixed)")

    schedule = {
        "startDate": START_DATE.isoformat(),
        "days": DAYS,
        "modes": {
            "classic": build_schedule(classic_pool, DAYS, SCHEDULE_SEED, "classic", keep["classic"]),
            "art": build_schedule(art_pool, DAYS, SCHEDULE_SEED + 1, "art", keep["art"]),
            "effect": build_schedule(effect_pool, DAYS, SCHEDULE_SEED + 2, "effect", keep["effect"]),
        },
    }
    path = os.path.join(GAME, "schedule.json")
    with _io.open(path, "w", encoding="utf-8") as fh:
        json.dump(schedule, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"schedule.json   {os.path.getsize(path)/1024:.0f} KB")

    # --- meta ---
    meta = {
        "builtFrom": fetched_at(),
        "poolSize": len(pool),
        "effectPoolSize": len(effect_pool),
        "startDate": START_DATE.isoformat(),
        "days": DAYS,
        "imageUrl": "https://digimoncard.app/assets/images/cards/{id}.webp",
        "imageFallback": "https://images.digimoncard.io/images/cards/{id}.jpg",
        "byCardType": dict(Counter(c["cardType"] for c in pool)),
    }
    with _io.open(os.path.join(GAME, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)

    # --- schedule quality report ---
    by_id = {c["id"]: c for c in pool}
    print("\nschedule quality (first 365 days, classic):")
    ids = schedule["modes"]["classic"]
    print("   distinct cards :", len(set(ids)))
    print("   card types     :", dict(Counter(by_id[i]["cardType"] for i in ids)))
    print("   rarities       :", dict(Counter(by_id[i]["rarity"] for i in ids).most_common()))
    name_gaps = {}
    worst = None
    for day, i in enumerate(ids):
        n = by_id[i]["name"]
        if n in name_gaps:
            gap = day - name_gaps[n]
            if worst is None or gap < worst[0]:
                worst = (gap, n)
        name_gaps[n] = day
    print("   closest name repeat:", worst or "none")
    print("\n   first 10 days:")
    for day, i in enumerate(ids[:10]):
        c = by_id[i]
        d = START_DATE + timedelta(days=day)
        print(f"     {d}  {i:10} {c['name'][:30]:32} {c['cardType']}")


if __name__ == "__main__":
    main()

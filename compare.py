"""Guess-vs-answer comparison rules for Classic mode.

Reference implementation. The browser will mirror this exactly; keeping a Python
copy means the rules can be tested against the real 4089-card pool instead of
being eyeballed in a UI.

The awkward part of a Digimon TCG dle is that Option and Tamer cards have no
Level, DP or Attribute at all. The rule that makes this work:

    both sides missing the field  ->  CORRECT

That is not a cop-out, it is real information. If you guess an Option card and
the DP cell comes back green-with-a-dash, the answer is also a card without DP,
which rules out all 3065 Digimon in one move.
"""

import io
import json
import os

# cell states
CORRECT = "correct"   # exact match (or both genuinely N/A)
PARTIAL = "partial"   # set overlap, or right family / wrong value
ABSENT = "absent"     # no match
HIGHER = "higher"     # numeric: the answer is higher than this guess
LOWER = "lower"       # numeric: the answer is lower than this guess

# Fields shown in the grid, in display order.
#
# Form used to sit between dp and attribute and is gone on purpose. It mostly
# restated Level — Rookie/Champion/Ultimate/Mega track Lv.3/4/5/6 almost one to
# one — and its "same evolution family" partial was too vague to act on. Rarity
# took the slot: plain right or wrong, with promos being their own rarity P.
GRID_FIELDS = [
    "cardType",
    "colors",
    "level",
    "playCost",
    "dp",
    "attribute",
    "types",
    "rarity",
    "setCode",
]


def _scalar(guess, answer):
    """Exact-match field. Both missing counts as a match."""
    if guess is None and answer is None:
        return CORRECT
    if guess == answer:
        return CORRECT
    return ABSENT


def _numeric(guess, answer):
    """Exact-match field with a direction hint when it misses."""
    if guess is None and answer is None:
        return CORRECT
    if guess is None or answer is None:
        return ABSENT
    if guess == answer:
        return CORRECT
    return HIGHER if answer > guess else LOWER


def _set(guess, answer):
    """List field: all-and-only -> correct, any overlap -> partial."""
    g, a = set(guess or []), set(answer or [])
    if not g and not a:
        return CORRECT
    if g == a:
        return CORRECT
    if g & a:
        return PARTIAL
    return ABSENT


def _load_set_dates():
    """{'BT1': '2021-01', ...} — English release month per set.

    Written by fetch_set_dates.py. P and LM are deliberately absent: "P" is
    every promo ever printed and "LM" covers LM-01 through LM-08, both spanning
    years, so neither has a release date to point at.
    """
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "data", "build", "set_dates.json")
    if not os.path.exists(path):
        return {}
    with io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


SET_DATES = None  # filled on first use


def _set_code(guess, answer):
    """Exact set -> correct; otherwise point at whether the answer's set is
    newer or older. Cards with no datable set (promos, limiteds) just miss."""
    global SET_DATES
    if SET_DATES is None:
        SET_DATES = _load_set_dates()
    if guess == answer:
        return CORRECT
    g, a = SET_DATES.get(guess), SET_DATES.get(answer)
    if not g or not a:
        return ABSENT
    return HIGHER if a > g else LOWER


_RULES = {
    "cardType": _scalar,
    "colors": _set,
    "level": _numeric,
    "playCost": _numeric,
    "dp": _numeric,
    "attribute": _scalar,
    "types": _set,
    "rarity": _scalar,
    "setCode": _set_code,
}


def compare(guess, answer):
    """Return {field: {state, value}} for one guess against the day's answer."""
    row = {}
    for field in GRID_FIELDS:
        g = guess.get(field)
        state = _RULES[field](g, answer.get(field))
        cell = {"state": state, "value": g}
        # a guess and answer that both lack the field: say so in the cell
        if state == CORRECT and g in (None, [], ""):
            cell["notApplicable"] = True
        row[field] = cell
    row["_solved"] = guess["id"] == answer["id"]
    return row


def is_solved(row):
    return row["_solved"]


# ---------------------------------------------------------------------------
# self-test against the real pool
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    from collections import Counter

    sys.stdout.reconfigure(encoding="utf-8")
    here = os.path.dirname(os.path.abspath(__file__))
    with io.open(os.path.join(here, "data", "build", "cards.json"), encoding="utf-8") as fh:
        cards = [c for c in json.load(fh) if c["inPool"]]
    by_id = {c["id"]: c for c in cards}

    def show(guess_id, answer_id):
        g, a = by_id[guess_id], by_id[answer_id]
        row = compare(g, a)
        print(f"\nguess {g['id']:9} {g['name'][:26]:28} vs answer {a['id']:9} {a['name'][:26]}")
        for field in GRID_FIELDS:
            cell = row[field]
            val = cell["value"]
            val = "/".join(map(str, val)) if isinstance(val, list) else val
            mark = {"correct": "OK ", "partial": "~  ", "absent": "X  ",
                    "higher": "X ^", "lower": "X v"}[cell["state"]]
            na = "  (neither has this)" if cell.get("notApplicable") else ""
            print(f"    {field:10} {str(val if val not in (None, '') else '—'):22} {mark}{na}")

    # a Digimon guessed against a Digimon
    show("ST1-03", "BT10-061")
    # an Option guessed against a Digimon: four dead columns
    show("BT2-096", "BT10-061")
    # an Option guessed against an Option: the dead columns become the clue
    opt = next(c for c in cards if c["cardType"] == "Option" and c["id"] != "BT2-096")
    show("BT2-096", opt["id"])
    # the answer itself
    show("BT10-061", "BT10-061")

    # --- sanity sweep: no crashes, and a correct guess is all-correct ---
    import random
    random.seed(11)
    states = Counter()
    for _ in range(20000):
        g, a = random.choice(cards), random.choice(cards)
        row = compare(g, a)
        for field in GRID_FIELDS:
            states[row[field]["state"]] += 1
    print("\n\n20k random comparisons, cell states:")
    for state, n in states.most_common():
        print(f"    {state:9} {n:7}  {100*n/sum(states.values()):5.1f}%")

    bad = [c["id"] for c in cards
           if not all(compare(c, c)[f]["state"] == CORRECT for f in GRID_FIELDS)]
    print(f"\ncards that fail self-comparison: {len(bad)} {bad[:5]}")

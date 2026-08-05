# digimondle — data pipeline

A daily "guess the card" game for the Digimon TCG. This folder currently holds
the data layer only.

## Running it

```bash
python fetch_data.py         # download raw sources -> data/raw/
python build_dataset.py      # merge + normalise    -> data/build/cards.json
python detect_sample.py all  # pick the clean image host per card (slow, optional)
python build_game_data.py    # browser payload      -> data/build/game/
python web/build_site.py     # inline it all        -> index.html
python compare.py            # run the guess-logic self-test
python profile_data.py       # optional: field distributions of the raw data
```

Open `index.html` — it is self-contained and runs from `file://`.

`fetch_data.py` and `detect_sample.py` are the only steps that touch the network.
Everything else rebuilds offline.

After a new set drops, `fetch_data.py` → `build_game_data.py` → `web/build_site.py`
is enough; re-run `detect_sample.py all` only when you care about watermarks on
the new cards.

## Sources

| Source | Role | Licence |
|---|---|---|
| [TakaOtaku/Digimon-Card-App](https://github.com/TakaOtaku/Digimon-Card-App) | base record — one row per card, names in 5 languages, ban list, alt-art count, rulings | MIT |
| [digimoncard.io public API](https://digimoncard.io/api-documentation) | set membership, tcgplayer ids, freshness check | public API, 15 req / 10s |

Both covered BT-26 / EX-12 / ST-24 at build time, so either alone is current;
they are merged because each has fields the other lacks.

Card ids are matched across sources with `norm_key()`, which strips leading
zeros (`RB1-10` and `RB1-010` are the same card). 4373 of 4399 cards matched;
the 26 that did not are brand-new BT-26 cards digimoncard.io had not indexed yet.

## Images

Loaded at runtime, never mirrored. Per player per day this is a handful of
requests, so hotlinking is not a burden on the host.

Default host is **digimoncard.app** — clean scans at 430×601, against
digimoncard.io's 300×419. `images.digimoncard.io` is the fallback: it is the
only one still carrying BT-26, and it is the only host that returns
`access-control-allow-origin: *`. That last part turned out not to matter, since
the art reveal is done with CSS `transform`/`filter` rather than canvas pixel
reads, so nothing gets tainted either way.

digimoncard.app answers a missing card with its SPA shell as `text/html` rather
than a 404, so the `<img onerror>` handler is what actually covers BT-26 — a
status check would not fire.

### The SAMPLE watermark

Neither host is reliably clean. Each stamps a large grey **SAMPLE** across a
different slice of the catalogue — digimoncard.app on BT22-088, digimoncard.io
on BT24-082. Across the full pool **430 of 4089 cards (10.5%) are watermarked on
one host and clean on the other**, which at one card a day is far too often to
ignore. 390 of those are watermarked on digimoncard.io, so the default host
already covers them; 28 are watermarked on digimoncard.app and get pinned to
digimoncard.io, along with 12 more that digimoncard.app simply does not carry.

`detect_sample.py` compares the two copies of every card and writes
`data/build/image_host.json` for the ones that need the non-default host;
`build_game_data.py` folds that into `cards.min.json` as a per-card `h` flag.

Getting this right took three attempts. Both dead ends are worth knowing about,
because both looked completely convincing until the output was eyeballed.

**Attempt 1 — "the lighter copy is the watermarked one."** SAMPLE is printed
light grey, so of the two copies the brighter one must be the bad one. Wrong:
the hosts often scanned *different printings*. BT1-010 Agumon has a silver frame
on one host and a red frame on the other, and neither is watermarked. This
mislabelled 118 cards.

**Attempt 2 — "the watermark is the difference that sits in the middle and
leaves the frame alone."** A watermark is text over the art; a different
printing differs everywhere, frame included. The numbers looked decisive:
BT24-082 had a middle/border ratio of 4.0 and BT22-088 of 63.2, against 1.7 and
0.4 for the reprints. Also wrong: cards get **errata**, and reworded rules text
is equally middle-only. BT1-048 Patamon reads "Reveal 4 cards from the top of
your deck" on one host and "Reveal the top 4 cards of your deck" on the other.
Erosion did not rescue it either — BT22-088's watermark is thin outline
lettering that erodes away *faster* than body text does.

**What works** is that the watermark is the same graphic every time: same font,
same position, same span, on every card that has it. So a reference template is
built from the intersection of three known-watermarked diffs, and a card counts
as watermarked only when its own diff reproduces that template.

| card | template overlap | |
|---|---|---|
| BT19-040 | **73.0%** | watermarked |
| BT24-082 | **63.2%** | watermarked |
| BT22-088 | **30.0%** | watermarked |
| BT1-089 | 8.8% | errata rewording |
| BT1-010 | 5.5% | different printing |
| ST1-03 | 0.8% | identical |

Threshold sits at 20%, with nothing between 8.8% and 30%. Six cards covering
watermarks, errata and reprints are asserted on every run, and the script
refuses to write its output if the calibration stops holding.

Spot-checking the pinned cards afterwards is worth the minute it takes — that is
what caught both earlier versions, and neither showed up in the numbers.

## Card record

```jsonc
{
  "id": "BT10-061",
  "name": "SkullKnightmon: Mighty Axe Mode",
  "names": { "english": "...", "japanese": "...", "korean": "...", ... },

  // guessable attributes
  "cardType": "Digimon",            // Digimon | Option | Tamer | Digi-Egg
  "colors": ["Black"],              // 1-3 entries
  "level": 4,                       // 2-7, null for Option/Tamer
  "playCost": 4,
  "dp": 5000,
  "form": "Champion",               // Rookie/Champion/Ultimate/Mega/Hybrid/...
  "attribute": "Virus",             // Vaccine/Virus/Data/Free/Variable/...
  "types": ["Enhancement", "Twilight"],
  "rarity": "C",
  "illustrator": "kaz",

  // set / release
  "setCode": "BT10", "setPrefix": "BT", "setCategory": "Booster",
  "blocks": ["02"],
  "printedIn": ["BT-10: Booster Xros Encounter"],
  "dateAdded": "2025-11-25 10:12:18",

  // rules text, for hint modes
  "effect": "...", "inheritedEffect": "...", "securityEffect": "...",
  "digivolveCondition": [{ "color": "Black", "cost": "3", "level": "3" }],
  "digiXros": "...", "dnaDigivolve": "...", "aceEffect": "...",
  "linkRequirement": "...", "linkDP": null, "rule": "...",

  "restriction": "Unrestricted",    // also: Restricted to 1 | Banned | Choice Restriction | Not released
  "released": true,
  "altArtCount": 3,
  "inPool": true,                   // eligible to be a daily answer
  "image": { "primary": "...", "fallback": "...", "official": "..." },
  "tcgplayerId": 229753
}
```

Fields that do not apply to a card are `null` or `[]`, never `"-"`.

### Caveat: `dateAdded` is not a release date

It is when digimoncard.io imported the row. ST1-03 (a 2020 card) reads
`2025-11-25`, and 86 distinct dates cover 15 years of releases. Do not use it to
ask "which year is this card from". Set code and `blocks` are the honest proxies
for release order; a real set→date table would have to be added by hand.

## What's in the pool

4399 cards total, 4089 flagged `inPool` (310 are Japan-only, not yet released in
English). Of the pool: 3065 Digimon, 483 Option, 306 Tamer, 235 Digi-Egg,
spread over 64 sets and 1816 distinct card names.

Level, play cost, DP, form and attribute only exist for Digimon — 2973 Digimon
have all five. Option and Tamer cards have colour, cost and rarity but nothing
else.

---

# Game layer

Three modes, all guessing a **specific card** (`Agumon ST1-03`, not `Agumon` —
38 different cards are called Agumon and they have different stats).

## Classic — the comparison grid

`compare.py` is the reference implementation; the browser mirrors it. Nine
columns: cardType, colors, level, playCost, dp, form, attribute, types, setCode.

Cell states: `correct`, `partial`, `absent`, plus `higher` / `lower` on the
numeric columns.

The rule that makes a mixed pool work is **both sides missing a field counts as
correct**. Guess an Option card and the Level/DP/Form/Attribute/Type cells come
back green-with-a-dash only if the answer is *also* a card without them — which
eliminates all 3065 Digimon in one guess. What looked like five dead columns is
the strongest single move in the game.

Partial credit: `colors` and `types` on any overlap; `form` within an evolution
family (Rookie/Champion/Ultimate/Mega are one family, Hybrid/Armor/D-Reaper
another); `setCode` on the same set line (any BT vs any BT).

Verified over 20k random pairings: 16.8% correct, 10.7% partial, 52.5% absent,
20% directional — and every card compares as all-correct against itself.

## Art — progressive reveal

Uses `image.primary`, the only CORS-enabled host, so the art can be cropped and
pixelated through a `<canvas>` without tainting it.

## Effect — guess from the rules text

Pool is 3902 cards (187 Digimon are vanilla with no text at all). The card's own
name is masked to `█████` in `effects.json` at build time, so the answer is
never shipped inside the puzzle.

Masking uses conditional word boundaries, not `\b` and not a plain replace.
A plain replace turns a reference to `[MetalGreymon]` into `[Metal█████]` when
the answer is Greymon — corrupting a mention of a *different* card and
half-leaking the answer. Plain `\b` breaks on names ending in punctuation like
`Dynasmon (X Antibody)`. Names shorter than four characters are skipped
entirely; there is a Tamer literally named `K`, and masking it would shred every
sentence. Verified: 0 whole-word leaks across all 3902 cards.

## Daily schedule

`schedule.json` holds a pre-rolled answer per day per mode, 365 days from
2026-08-05. No server, no database — the browser looks up today's index.

Picks are drawn **without replacement**, so no card repeats inside a year (365
days, 365 distinct cards in every mode). Same Digimon name stays ≥60 days apart,
same set ≥5 days apart; the closest name repeat in the current roll is 62 days.
Selection is weighted by a rough recognisability proxy — reprint count, alt-art
count, rarity, plus a bump for banned/restricted cards — which is why the year
skews to 260 Digimon / 52 Tamer / 36 Option / 17 Digi-Egg rather than matching
the raw pool ratios.

Rerolling: change `SCHEDULE_SEED` in `build_game_data.py`. Same seed always
gives the same year, so a rebuild after a new set drops does not shuffle days
that have already been played.

## Endless

Every mode has a Daily and an Endless side. Endless deals from a shuffled queue
of the whole pool and pops as it goes, so it exhausts all 4089 cards before it
repeats one — verified by drawing 500 in a row with no duplicate. Nothing is
saved and nothing touches the streak.

## Searching

Players say "bt14 agumon", not "Agumon, BT14-086", and "greymon x" rather than
typing out "Greymon (X Antibody)". So the query is tokenised and every token has
to land somewhere — name, card number, or set code — with name hits scoring
above number hits. That ranking is what floats Greymon (X Antibody) above the
EX-set Greymons for "greymon x": the `x` in `EX5-011` is a real but much weaker
hit than the `x` in the name.

ACE rides along as an extra name token. It is printed on the card face but is
not part of any card's name, so `metalgreymon ace` would otherwise find nothing.

One trap worth remembering: the whole-query exact-id bonus only applies when the
query has no spaces. `norm()` strips whitespace, so `"bt10 61"` collapses to
`"bt1061"` and scored a spurious exact-id hit on Mistymon (BT1-061).

## Browser payload

`web/build_site.py` inlines everything into a single `index.html`, so it works
from `file://` by double-clicking as well as over HTTP. Card images still come
from the network at play time, which is the point — a new set does not require
rebuilding the page.

| Block | Size |
|---|---|
| `cards.min.json` | 684 KB — grid data + autocomplete for 4089 cards |
| `effects.json` | 1.06 MB |
| `schedule.json` | 11 KB |
| `meta.json` | <1 KB |
| **`index.html`** | **1.87 MB** |

Keys in `cards.min.json` are shortened (`n`, `t`, `c`, `lv`…) with the mapping
shipped in the file's own `keys` field. Image URLs are omitted because they are
a pure function of the id — storing them would nearly double the payload.

### Two bugs worth not reintroducing

`loading="lazy"` on the art-mode image deadlocks it. The image is sized
`height:auto`, so before it loads it is 0px tall — and a zero-height lazy image
never comes close enough to the viewport to start loading, so it stays 0px tall
forever, with an empty `currentSrc`. There is no `loading="lazy"` in the page.

The art window is a 3:2 slit, not a square, and it has a hard floor. Rules text
on a Digimon card is printed **over** the art at about 58% of the card height,
and there is a thumbnail of the same Digimon in the inherited-effect box near the
bottom. The slit stays inside 24%–52% of the card height at every zoom; a square
window at the same widest setting would have run past 62% and shown the text.

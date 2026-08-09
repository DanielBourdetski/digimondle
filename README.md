# Digimondle

A daily "guess the card" game for the Digimon TCG.

**Play: https://galpartuk.github.io/digimondle/**

`index.html` is self-contained and also runs by double-clicking it — card images
are the only thing it fetches, so it needs a connection for those.

## Running it

```bash
python fetch_data.py         # download raw sources  -> data/raw/
python build_dataset.py      # merge + normalise     -> data/build/cards.json
python fetch_set_dates.py    # English release dates -> data/build/set_dates.json
python detect_sample.py all  # clean image host per card (slow: ~8000 downloads)
python build_game_data.py    # browser payload       -> data/build/game/
python web/build_site.py     # inline it all         -> index.html

python compare.py            # guess-logic self-test against the real pool
node web/test_logic.js       # the same logic, headless, as the browser runs it
python profile_data.py       # optional: field distributions of the raw data
```

`fetch_data.py`, `fetch_set_dates.py` and `detect_sample.py` are the only steps
that touch the network. Everything else rebuilds offline, and their outputs are
committed so a clone can go straight to `build_game_data.py`.

After a new set drops: `fetch_data.py` → `build_dataset.py` → `fetch_set_dates.py`
→ `build_game_data.py` → `web/build_site.py` → commit → push. Pages redeploys
itself in about a minute. Re-run `detect_sample.py all` only when you care about
watermarks on the new cards.

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

Level, play cost, DP and attribute only exist for Digimon. Option and Tamer cards have colour, cost and rarity but nothing
else.

---

# Game layer

Three modes, all guessing a **specific card** (`Agumon ST1-03`, not `Agumon` —
38 different cards are called Agumon and they have different stats).

## Classic — the comparison grid

`compare.py` is the reference implementation; the browser mirrors it, and
`web/test_logic.js` asserts they agree. Nine columns: cardType, colors, level,
playCost, dp, attribute, types, rarity, setCode.

Cell states: `correct`, `partial`, `absent`, plus `higher` / `lower` on the
numeric columns and on Set.

**Form is deliberately not a column.** It mostly restated Level —
Rookie/Champion/Ultimate/Mega track Lv.3/4/5/6 almost one to one — and its
"same evolution family" partial was too vague to act on. Rarity took the slot,
as a plain right-or-wrong with promos being their own rarity `P`.

The rule that makes a mixed pool work is **both sides missing a field counts as
correct**. Guess an Option card and the Level/DP/Attribute/Type cells come
back green-with-a-dash only if the answer is *also* a card without them — which
eliminates all 3065 Digimon in one guess. What looked like four dead columns is
the strongest single move in the game.

Partial credit is only for `colors` and `types`, on any overlap. Everything else
is right or wrong.

Rarity points too, on `C < U < R < SR < UR < SEC < P`. The tail is a judgement
call rather than a pull-rate fact — promos are not "rarer" than a Secret Rare,
they come from a different channel — but an arrow needs a total order, and
promos on top is how players talk about them. The whole **LM** line is treated as
a promo channel, so its cards ship with rarity `P` regardless of what their pack
happened to print.

Verified over 20k random pairings: 17.7% correct, 1.6% partial, 51.2% absent,
29.4% directional — and every card compares as all-correct against itself.

### The Set column points in time

Not at the set number. `set_dates.json` holds the English release month of every
set, so ↑ means the answer is from a later release than the card you guessed.

The card data has no usable release date of its own — digimoncard.io's
`date_added` is when the row was imported, which puts every set older than the
import on 2025-11-25 — so `fetch_set_dates.py` scrapes the DigimonCardGame
wiki's set-list pages, which group releases under `===Month, Year===` headings.

Two things there are easy to get wrong:

- The page is a **five-tab tabber** (Worldwide, English, Japanese, Chinese,
  Korean) and the Japanese tab lists the same sets months earlier. Both English
  tabs are needed, not one: Bandai only unified releases in April 2025, so
  "Worldwide" covers 2025-04 onward and everything older is under "English".
- The English releases **bundled sets into version products**, listed under a
  version code rather than a set code. Reading `BT2.0` as `BT2` is not a miss,
  it is wrong data — it dated BT-02 to November 2024 when BT-02 actually shipped
  in the Ver.1.0 bundle in January 2021. `BUNDLES` maps the four of them, with
  contents confirmed against `printedIn` in our own card data.

Result: all 62 datable sets covered, and BT-01 … BT-26 come out strictly
monotonic in time. Sets from different lines interleave — BT-18 and BT-19 both
landed in November 2024, EX-08 sits between BT-19 and BT-20 — which is exactly
the information the arrow carries and the set number does not.

`P` and `LM` carry no arrow. Neither is a set: `P` is every promo ever printed,
and `LM` covers LM-01 through LM-08. Both span years, so there is nothing
honest to point at.

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

## What is in the pool

`restrictions.english == "Not released"` from the source data goes stale badly:
it still had all 74 EX-11 cards and 75 of EX-12 flagged unreleased months after
both sets were on shelves, quietly keeping 157 real cards out of the game.

So membership is decided by **belonging to a set with an English release date**,
and that date is deliberately *not* compared against today — a spoiled BT-26
card is a card people have seen and can name. The stale flag only gets a say for
`P` and `LM`, which are not single sets, have no date, and are where the
genuinely Japan-only cards live.

Pool: 4327 of 4399. The 72 left out are 31 LM and 28 P that never released in
English, plus 13 BT-26 rows whose name in the source is the literal string
`[[:Category:|]]` — wiki markup that leaked into the data.

### Adding cards reshuffles the year, so days already played are frozen

The schedule draws without replacement from the pool, so inserting a card
changes every draw after it. A rebuild after a new set would silently rewrite
answers people had already played. `build_schedule()` therefore holds the first
`days_elapsed() + 1` entries of the previous `schedule.json` fixed and only
re-rolls from tomorrow on. Today counts as spoken for — its answer is live.

## The streak

A day is earned by solving **all three** daily modes. That rule is not
guessable, so a bar at the top names the modes still outstanding rather than
merely counting them, and the marker beside the memory gauge **digivolves** with
the run: Fresh, In-Training, Rookie, Champion, Ultimate, Mega at twenty days.
The egg picks up a crack, then splits, then hatches.

The counting had two bugs worth not reintroducing. It used to key off
`day + ":" + mode`, so playing all three modes scored **+3** — and because
nothing was ever compared against yesterday, a streak **survived skipping a
week**. Both were invisible while the number sat in a text line; they are not
once it has a badge.

Nothing runs on the days a player does not open the page, so a broken run is
worked out on read rather than on write: a streak whose last earned day is older
than yesterday is over. Yesterday still counts as alive, because today is not
finished yet.

`migrateStats()` rebuilds the ledger for anyone who was already playing when the
rule changed. The round state is the way back — `persist()` has always saved a
`{a,g,o,w}` entry per mode per day and keeps a week of them, and `w` means
exactly "this mode was solved that day". The streak is then recounted from that
ledger instead of trusting the old number. It is idempotent, so it runs on every
load.

### Moving a streak between browsers

Everything lives in `localStorage`, so a new device or a cleared cache starts at
nothing. "Move your streak" produces a code to paste into the other browser:

```
DGDLE1-eyJ2IjoxLCJiIjo0LCJwIjo0LCJ3IjoxMywiRCI6W1stMyw3XSxbLTIsN10...-7r21
```

Three decisions in there are worth keeping:

- **The code carries the day ledger, not the streak number**, and the streak is
  recounted from those days on the way in. A code cannot claim a run its days do
  not support — a forged one with an empty ledger imports as zero.
- **Days are absolute indices** from the schedule's start date, so a code means
  the same thing on any device in any timezone.
- **Restoring merges, it does not overwrite.** Importing on a machine where you
  have already played today keeps today.

The trailing four characters are a checksum, so a mistyped code is refused
outright rather than importing quietly broken data. Roughly 100 characters for a
month of history.

## Endless

Every mode has a Daily and an Endless side. Endless deals from a shuffled queue
and pops as it goes, so it exhausts the pool before repeating anything —
verified by drawing 1200 in a row with no duplicate. Nothing is saved and
nothing touches the streak.

### Pool filters

Daily is the same card for everyone and stays that way. Endless is yours, so it
gets a panel — visible only in Endless — that narrows what can come up: a span
of sets, plus a toggle per rarity. Choices persist in `localStorage`.

Sets are ordered by **release date**, not by number, because the numbers
interleave: EX-08 shipped between BT-19 and BT-20. So a range of BT-20 to BT-26
also sweeps in the EX, ST and AD sets released in between, which is why the
panel reports how many sets survived rather than only the count of cards. `P`
and `LM` are not on that line at all — neither is a single set — so they are
toggles of their own rather than range endpoints.

Filtering only ever narrows the **answers**. Every card stays guessable; a
filter that also restricted guesses would just be annoying. If a combination
matches nothing, Endless falls back to the full pool rather than dealing
`undefined` forever.

The filter is also why pool membership now requires a rarity. BT26-091 has a
name and an effect but no rarity, no illustrator and no art on either host — an
incomplete spoiler row rather than a card. It matched no rarity checkbox, so it
could never be dealt no matter what you picked; now it is not in the pool at all.

## Searching

Players say "bt14 agumon", not "Agumon, BT14-086", and "greymon x" rather than
typing out "Greymon (X Antibody)". So the query is tokenised and every token has
to land somewhere — name, card number, or set code — with name hits scoring
above number hits. That ranking is what floats Greymon (X Antibody) above the
EX-set Greymons for "greymon x": the `x` in `EX5-011` is a real but much weaker
hit than the `x` in the name.

ACE rides along as an extra name token. It is printed on the card face but is
not part of any card's name, so `metalgreymon ace` would otherwise find nothing.

Each suggestion row shows the card's thumbnail, colour chips, card type, number
and rarity, tinted from SR upward so the scarce printings stand out without a
second lookup.

The list holds 12 and scrolls. A silent cut was the wrong behaviour here,
because it bites hardest exactly where people search most: `Greymon` matches
**148** cards, `X Antibody` 107, `Agumon` 75 — 100 of the 1,889 card names
overflow. Showing eight and saying nothing left no way to know more existed, let
alone how to reach them. So the last row names the count and hands over a query
that works, built from the set the top hit came from:

```
+136 more — add a set, like  ad1 greymon
```

That row is also the only place the multi-token search teaches itself, and it
appears at the moment it is useful. A test checks the suggested query really
does narrow the list, so the tip cannot rot into bad advice.

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

There is no blur, on either the art window or the hint peek. The crop already
does the work, and stacking a blur on top of a 3.8x zoom made the early frames
unreadable rather than hard.

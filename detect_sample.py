"""Work out which image host has the clean scan of each card.

Neither host is reliably clean. Each stamps a large grey SAMPLE across a
different slice of the catalogue — digimoncard.app on BT22-088, digimoncard.io
on BT24-082 — so the two copies get compared and the watermarked one dropped.

Getting this right took three attempts, and the two dead ends are the reason
this file works the way it does:

  1. "The lighter copy is the watermarked one." Wrong: the hosts often scanned
     *different printings*. BT1-010 Agumon has a silver frame on one and a red
     frame on the other and neither is watermarked.
  2. "The watermark is the difference that sits in the middle and leaves the
     frame alone." Also wrong: cards get **errata**, and reworded rules text is
     equally middle-only. BT1-048 Patamon reads "Reveal 4 cards from the top of
     your deck" on one host and "Reveal the top 4 cards of your deck" on the
     other. Erosion did not separate them either — BT22-088's watermark is thin
     outline lettering that erodes away faster than body text does.

What does work: the watermark is the *same graphic every time*. Same font, same
place, same span, on every card that has it. So a reference template is built
from the diff of three known-watermarked cards, and a card counts as
watermarked only when its own diff reproduces that template.

    card       overlap   truth
    BT19-040    73.0%    watermark
    BT24-082    63.2%    watermark
    BT22-088    30.0%    watermark
    BT1-089      8.8%    errata rewording
    BT1-010      5.5%    different printing
    ST1-03       0.8%    identical

Run with a card count to sample, or "all" to check the whole pool.
"""

import io as _io
import json
import os
import sys
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ImageChops, ImageStat

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "data", "build")

UA = "digimondle-sampledetect/1.0 (personal hobby project)"
SIZE = (300, 420)
BAND = (0, int(420 * 0.34), 300, int(420 * 0.58))   # where SAMPLE always lands

DIFF_THRESHOLD = 30    # per-pixel grey difference that counts as "these differ"
MIN_OVERLAP = 0.20     # share of the template a real watermark reproduces

# cards whose watermark defines the template — all watermarked on digimoncard.io
TEMPLATE_CARDS = ["BT19-005", "BT19-049", "BT20-035"]

# asserted on every run; if these stop holding, the detector is not trustworthy
CALIBRATION = {
    "BT24-082": "app",      # io watermarked
    "BT22-088": "io",       # app watermarked
    "BT1-048": "either",    # errata rewording, not a watermark
    "BT1-089": "either",    # errata rewording
    "BT1-010": "either",    # different printing
    "BT1-003": "either",    # different printing
}

APP = "https://digimoncard.app/assets/images/cards/{}.webp"
IO = "https://images.digimoncard.io/images/cards/{}.jpg"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as resp:
        if not resp.headers.get("Content-Type", "").startswith("image/"):
            return None
        return Image.open(_io.BytesIO(resp.read())).convert("L").resize(SIZE)


def binary(mask):
    return mask.point(lambda p: 255 if p else 0)


def band_diff(a, b):
    """Binary mask of where the two copies disagree, cropped to the SAMPLE band."""
    d = ImageChops.difference(a, b).point(lambda p: 255 if p > DIFF_THRESHOLD else 0)
    return d.crop(BAND)


def build_template():
    """Intersect several known watermarks so only the shared glyphs survive."""
    masks = []
    for cid in TEMPLATE_CARDS:
        a, b = fetch(APP.format(cid)), fetch(IO.format(cid))
        if a and b:
            masks.append(binary(band_diff(a, b)))
    if not masks:
        raise SystemExit("could not fetch the template cards")
    tpl = masks[0]
    for m in masks[1:]:
        tpl = binary(ImageChops.multiply(tpl, m))
    return tpl, tpl.histogram()[255]


TEMPLATE = TEMPLATE_PIXELS = None


def verdict(card_id):
    """Return (id, host_with_clean_scan, template overlap)."""
    try:
        a, b = fetch(APP.format(card_id)), fetch(IO.format(card_id))
    except Exception:
        return card_id, "error", 0.0
    if a is None and b is None:
        return card_id, "error", 0.0
    if a is None:
        return card_id, "io", 0.0
    if b is None:
        return card_id, "app", 0.0

    mask = binary(band_diff(a, b))
    hit = binary(ImageChops.multiply(mask, TEMPLATE)).histogram()[255]
    overlap = hit / TEMPLATE_PIXELS if TEMPLATE_PIXELS else 0.0
    if overlap < MIN_OVERLAP:
        return card_id, "either", overlap

    # SAMPLE is printed light, so the brighter copy inside the glyphs is the bad one
    mean_a = ImageStat.Stat(a.crop(BAND), mask).mean[0]
    mean_b = ImageStat.Stat(b.crop(BAND), mask).mean[0]
    return card_id, ("io" if mean_a > mean_b else "app"), overlap


def main():
    global TEMPLATE, TEMPLATE_PIXELS
    arg = sys.argv[1] if len(sys.argv) > 1 else "40"

    with _io.open(os.path.join(BUILD, "cards.json"), encoding="utf-8") as fh:
        pool = [c["id"] for c in json.load(fh) if c["inPool"]]

    TEMPLATE, TEMPLATE_PIXELS = build_template()
    print(f"template built from {', '.join(TEMPLATE_CARDS)} — {TEMPLATE_PIXELS} px\n")

    if arg == "all":
        ids = pool
    else:
        import random
        random.seed(5)
        ids = random.sample(pool, min(int(arg), len(pool)))
    for known in CALIBRATION:
        if known in pool and known not in ids:
            ids.append(known)

    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(verdict, ids))

    counts = Counter(v for _, v, _ in results)
    total = sum(counts.values())
    print(f"checked {total} cards")
    for k in ("either", "app", "io", "error"):
        if counts[k]:
            note = {"either": "no watermark (identical, or a reprint/errata difference)",
                    "app": "digimoncard.app is clean (io watermarked)",
                    "io": "digimoncard.io is clean (app watermarked)",
                    "error": "could not compare"}[k]
            print(f"  {k:7} {counts[k]:4}  {100*counts[k]/total:5.1f}%   {note}")

    print("\ncalibration:")
    ok = True
    for cid, v, overlap in results:
        if cid in CALIBRATION:
            good = v == CALIBRATION[cid]
            ok &= good
            print(f"  {cid:9} -> {v:7} (want {CALIBRATION[cid]:7}) "
                  f"overlap {overlap*100:5.1f}%  {'OK' if good else 'WRONG'}")
    if not ok:
        print("\n  !! calibration failed — do not trust this run")
        return

    if arg == "all":
        clean = {cid: v for cid, v, _ in results if v in ("app", "io")}
        out = os.path.join(BUILD, "image_host.json")
        with _io.open(out, "w", encoding="utf-8") as fh:
            json.dump(clean, fh, indent=0, sort_keys=True)
        print(f"\nwrote {out} ({len(clean)} watermarked cards routed to the other host)")


if __name__ == "__main__":
    main()

"""Download the raw Digimon TCG card data we build the game from.

Sources:
  1. TakaOtaku/Digimon-Card-App (MIT)  - rich, multilingual, alt-art list, ban list
  2. digimoncard.io public API         - freshest, has release dates + set membership

Both are written to data/raw/ as-is so a rebuild never needs the network.
"""

import json
import os
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "raw")

SOURCES = {
    "takaotaku_cards.json": "https://raw.githubusercontent.com/TakaOtaku/Digimon-Card-App/main/src/assets/cardlists/DigimonCards.json",
    "takaotaku_rulings.json": "https://raw.githubusercontent.com/TakaOtaku/Digimon-Card-App/main/src/assets/cardlists/Rulings.json",
    "digimoncard_io.json": "https://digimoncard.io/api-public/search.php?sort=name&series=Digimon%20Card%20Game",
}

UA = "digimondle-datafetch/1.0 (personal hobby project)"


def fetch(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = resp.read()
    data = json.loads(body.decode("utf-8"))
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)
    return len(body), len(data)


def main():
    os.makedirs(RAW, exist_ok=True)
    for name, url in SOURCES.items():
        dest = os.path.join(RAW, name)
        try:
            size, count = fetch(url, dest)
            print(f"  ok   {name:24} {size/1e6:6.2f} MB  {count:5} records")
        except Exception as exc:
            print(f"  FAIL {name:24} {exc}")
        time.sleep(1)  # digimoncard.io allows 15 req / 10s; be polite

    stamp = os.path.join(RAW, "fetched_at.txt")
    with open(stamp, "w", encoding="utf-8") as fh:
        fh.write(time.strftime("%Y-%m-%d %H:%M:%S"))


if __name__ == "__main__":
    main()

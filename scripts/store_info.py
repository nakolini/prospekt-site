"""Fetches Prospekt's App Store name, price and version for each site language.

Usage: python3 scripts/store_info.py   (then make build, and commit data/store.json)

Uses Apple's public lookup API, one storefront per language. Arabic has no
single storefront, so it uses the US one.
"""

import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gen"))
import build  # noqa: E402

STOREFRONTS = {"en": "us", "ar": "us", "de": "de", "es": "es", "fr": "fr", "it": "it", "ja": "jp", "ko": "kr",
               "nl": "nl", "pl": "pl", "pt-BR": "br", "tr": "tr", "uk": "ua", "zh-Hans": "cn", "zh-Hant": "tw"}
# The lookup formats Taiwan dollars as a bare "$".
PRICE_FIXES = {"tw": lambda p: "NT" + p if p.startswith("$") else p}


def main():
    out = {}
    for code, country in STOREFRONTS.items():
        url = "https://itunes.apple.com/lookup?id=%s&country=%s" % (build.APP_ID, country)
        with urllib.request.urlopen(url, timeout=30) as response:
            result = json.load(response)["results"][0]
        price = result["formattedPrice"]
        price = PRICE_FIXES.get(country, lambda p: p)(price)
        out[code] = {"storefront": country, "name": result["trackName"], "price": price,
                     "version": result["version"], "released": result["currentVersionReleaseDate"][:10]}
    with open(os.path.join(build.ROOT, "data", "store.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("store.json: %d languages, version %s" % (len(out), out["en"]["version"]))


if __name__ == "__main__":
    main()

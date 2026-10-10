"""Tells IndexNow search engines (Bing, Yandex, Seznam, Naver) about every page.

Usage: python3 scripts/indexnow.py   (after the build is deployed)

Reads the URLs from sitemap.xml. The key file <INDEXNOW_KEY>.txt must already
be live at the site root, or the engines reject the submission.
"""

import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gen"))
import build  # noqa: E402

ENDPOINT = "https://api.indexnow.org/indexnow"


def main():
    with open(os.path.join(build.ROOT, "sitemap.xml"), encoding="utf-8") as f:
        urls = re.findall(r"<loc>([^<]+)</loc>", f.read())
    host = build.BASE_URL.split("://", 1)[1].split("/", 1)[0]
    payload = {
        "host": host,
        "key": build.INDEXNOW_KEY,
        "keyLocation": "%s/%s.txt" % (build.BASE_URL, build.INDEXNOW_KEY),
        "urlList": urls,
    }
    request = urllib.request.Request(
        ENDPOINT, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8",
                 # api.indexnow.org answers urllib's default "Python-urllib" agent with 403.
                 "User-Agent": "prospekt-site-indexnow/1.0 (+" + build.BASE_URL + ")"},
        method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        print("IndexNow: HTTP %d for %d URLs" % (response.status, len(urls)))


if __name__ == "__main__":
    main()

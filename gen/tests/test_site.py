"""Checks the committed, built site: run `make build` first."""

import glob
import os
import re
import sys
import unittest
from html.parser import HTMLParser

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(HERE, ".."))
import build  # noqa: E402


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []
        self.hreflangs = []
        self.canonical = None
        self.h1 = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and "href" in attrs:
            self.hrefs.append(attrs["href"])
        if tag in ("img", "script") and attrs.get("src"):
            self.hrefs.append(attrs["src"])
        if tag == "link" and attrs.get("rel") == "stylesheet":
            self.hrefs.append(attrs["href"])
        if tag == "link" and attrs.get("rel") == "alternate":
            self.hreflangs.append(attrs["hreflang"])
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical = attrs["href"]
        if tag == "h1":
            self.h1 += 1


def pages():
    return sorted(p for p in glob.glob(os.path.join(ROOT, "**", "index.html"), recursive=True)
                  if "/.git/" not in p and "/node_modules/" not in p)


class SiteTest(unittest.TestCase):
    def test_page_count(self):
        langs = len(build.load_languages())
        self.assertEqual(len(pages()), langs * (4 + 59))

    def test_every_page_is_complete_without_javascript(self):
        for path in pages():
            with open(path, encoding="utf-8") as f:
                text = f.read()
            parser = Links()
            parser.feed(text)
            rel = os.path.relpath(path, ROOT)
            with self.subTest(page=rel):
                self.assertEqual(parser.h1, 1)
                self.assertTrue(parser.canonical.startswith(build.BASE_URL + "/"))
                self.assertEqual(len(parser.hreflangs), len(build.load_languages()) + 1)
                self.assertIn("apps.apple.com/app/apple-store/id%s" % build.APP_ID, text)
                visible = re.sub(r'<script type="application/json".*?</script>', "", text, flags=re.S)
                leftover = re.search(r"\{[a-z_0-9.]+\}", visible)
                self.assertIsNone(leftover, leftover and leftover.group(0))
                for href in parser.hrefs:
                    if re.match(r"^(https?:|mailto:|#)", href):
                        continue
                    target = os.path.normpath(os.path.join(os.path.dirname(path), href.split("?")[0]))
                    if href.split("?")[0].endswith("/"):
                        target = os.path.join(target, "index.html")
                    self.assertTrue(os.path.exists(target), "broken link %s" % href)

    def test_price_is_in_the_html(self):
        with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
            self.assertIn("$3.99", f.read())

    def test_robots_and_sitemap(self):
        with open(os.path.join(ROOT, "robots.txt")) as f:
            robots = f.read()
        self.assertIn("User-agent: GPTBot\nAllow: /", robots)
        self.assertNotIn("Disallow", robots)
        with open(os.path.join(ROOT, "sitemap.xml")) as f:
            sitemap = f.read()
        self.assertEqual(sitemap.count("<url>"), len(pages()) + 3)

    def test_custom_domain_and_indexnow_key(self):
        with open(os.path.join(ROOT, "CNAME")) as f:
            self.assertEqual("https://" + f.read().strip(), build.BASE_URL)
        with open(os.path.join(ROOT, build.INDEXNOW_KEY + ".txt")) as f:
            self.assertEqual(f.read().strip(), build.INDEXNOW_KEY)


if __name__ == "__main__":
    unittest.main()

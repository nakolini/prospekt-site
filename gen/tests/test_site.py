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
        # Home, tool, cameras, changelog, 59 cameras, the guides hub, comparisons and guides.
        self.assertEqual(len(pages()), langs * (4 + 59 + 1 + len(build.COMPARISONS) + len(build.GUIDES)))

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

    def test_every_camera_page_has_distance_tables(self):
        body_pages = [p for p in pages() if re.search(r"/cameras/[^/]+/index\.html$", p)]
        self.assertEqual(len(body_pages), len(build.load_languages()) * 59)
        crops = {b["slug"]: b["crop"] for b in build.load_bodies()}
        for path in body_pages:
            with open(path, encoding="utf-8") as f:
                text = f.read()
            with self.subTest(page=os.path.relpath(path, ROOT)):
                table = re.search(r'<table class="distances">.*?</table>', text, re.S)
                self.assertIsNotNone(table)
                self.assertEqual(table.group(0).count("<tr>"), 1 + len(build.lm.COVERAGE_FOCAL_LENGTHS))
                self.assertEqual(table.group(0).count("<td>"),
                                 len(build.lm.COVERAGE_FOCAL_LENGTHS) * len(build.lm.COVERAGE_DISTANCES))
                portraits = re.search(r'<ul class="portraits">(.*?)</ul>', text, re.S)
                self.assertEqual(portraits.group(1).count("<li>"), len(build.lm.PORTRAIT_FOCAL_LENGTHS))
                faq = re.search(r'"@type": "FAQPage".*?</script>', text, re.S).group(0)
                # Full frame skips the "what is my crop factor" question.
                full_frame = crops[os.path.basename(os.path.dirname(path))] == 1.0
                self.assertEqual(faq.count('"@type": "Question"'), 5 if full_frame else 6)

    def test_distance_numbers_on_a_full_frame_and_a_crop_body(self):
        # 85 mm full body: 2 m of frame height over 36 mm -> 4.7 m; x1.5 on APS-C -> 7.1 m.
        # 35 mm at 3 m on full frame: 3.1 x 2.1 m.
        with open(os.path.join(ROOT, "cameras", "sony-a7-iv", "index.html"), encoding="utf-8") as f:
            ff = f.read()
        self.assertIn("About 4.7\u00a0m (15\u00a0ft) from the subject", ff)
        self.assertIn("About 3.1\u00a0\u00d7 2.1\u00a0m, width by height", ff)
        with open(os.path.join(ROOT, "cameras", "sony-a6700", "index.html"), encoding="utf-8") as f:
            self.assertIn("About 7.1\u00a0m (23\u00a0ft) from the subject", f.read())
        with open(os.path.join(ROOT, "de", "cameras", "sony-a7-iv", "index.html"), encoding="utf-8") as f:
            self.assertIn("4,7\u00a0m (15\u00a0ft)", f.read())

    def test_tool_page_has_static_distance_content(self):
        with open(os.path.join(ROOT, "lens-compare", "index.html"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn('<table class="distances">', text)
        self.assertIn('<ul class="portraits">', text)
        self.assertIn('id="body2"', text)
        self.assertIn('data-zoom="24-70"', text)

    def test_assets_are_versioned_by_content(self):
        # A deploy changes the ?v= of a changed file, so cached CSS or JS never meets new pages.
        css = build.asset_url("assets/site.css")
        js = build.asset_url("assets/lens-compare.js")
        self.assertRegex(css, r"^assets/site\.css\?v=[0-9a-f]{10}$")
        for path in pages():
            with open(path, encoding="utf-8") as f:
                text = f.read()
            with self.subTest(page=os.path.relpath(path, ROOT)):
                self.assertIn(css + '"', text)
                self.assertNotIn('site.css"', text)
                self.assertEqual("lens-compare/" in path.replace(os.sep, "/"), js + '"' in text)

    def test_tool_page_is_light_and_labelled(self):
        with open(os.path.join(ROOT, "lens-compare", "index.html"), encoding="utf-8") as f:
            text = f.read()
        # Phones get the 1200 px photo, and the no-script figure is hidden before it loads.
        self.assertIn('srcset="../assets/sample-14mm-1200.jpg 1200w, ../assets/sample-14mm.jpg 1920w"', text)
        self.assertIn('document.documentElement.className += " js"', text)
        self.assertIn('data-focal="24" aria-pressed="true" aria-label="24 mm">24</button>', text)
        self.assertIn('aria-label="24-70 mm">24-70</button>', text)
        self.assertIn('role="radiogroup" aria-label="Frame orientation"', text)
        # The camera list is in the tool's JSON, so its quotes are escaped.
        self.assertIn('data-label=\\"Full frame, 1x\\"', text)
        self.assertIn('<table class="equiv">', text)

    def test_comparison_pages(self):
        for pair in build.COMPARISONS:
            path = os.path.join(ROOT, build.compare_path(pair), "index.html")
            with open(path, encoding="utf-8") as f:
                text = f.read()
            with self.subTest(pair=pair["a"]):
                self.assertIn('href="../../lens-compare/?f=%d,%d"' % (pair["a"], pair["b"]), text)
                self.assertEqual(text.count("ct=web_compare_line"), 1)
                self.assertEqual(text.count('class="app-line"'), 1)
                self.assertEqual(re.search(r'<table class="pair">.*?</table>', text, re.S).group(0).count('class="group"'),
                                 len(build.FORMAT_CROPS))
                faq = re.search(r'"@type": "FAQPage".*?</script>', text, re.S).group(0)
                self.assertEqual(faq.count('"@type": "Question"'), 3)
                self.assertIn('"mentions": {"@type": "MobileApplication", "@id": "%s"' % build.APP_ENTITY_ID, text)
                self.assertIn('"@type": "BreadcrumbList"', text)
                self.assertIn('href="../../guides/"', text)
        # 35 mm at 3 m on full frame: 3.1 x 2.1 m; 50 mm full body at 2.8 m; 23 and 33 mm on APS-C.
        with open(os.path.join(ROOT, "compare", "35mm-vs-50mm", "index.html"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("<h1>35 mm vs 50 mm: which should you choose?</h1>", text)
        self.assertIn("35 mm sees 54.4° across and covers 3.1\u00a0\u00d7 2.1\u00a0m at 3 m", text)
        self.assertIn("about 1.9\u00a0m (6.4\u00a0ft) with 35 mm and 2.8\u00a0m (9.1\u00a0ft) with 50 mm", text)
        self.assertIn("use about 23 mm and 33 mm", text)

    def test_guide_pages(self):
        for guide in build.GUIDES:
            with open(os.path.join(ROOT, build.guide_path(guide), "index.html"), encoding="utf-8") as f:
                text = f.read()
            with self.subTest(guide=guide["slug"]):
                focals = ",".join(str(f) for f in sorted(guide["recs"]))
                self.assertIn('href="../../lens-compare/?f=%s"' % focals, text)
                self.assertEqual(text.count("ct=web_guide_line"), 1)
                self.assertEqual(re.search(r'<table class="recs">.*?</table>', text, re.S).group(0).count("<tr>"),
                                 1 + len(guide["recs"]))
                faq = re.search(r'"@type": "FAQPage".*?</script>', text, re.S).group(0)
                self.assertEqual(faq.count('"@type": "Question"'), 3)
                self.assertEqual('<ul class="portraits">' in text, bool(guide.get("portraits")))
        with open(os.path.join(ROOT, "focal-length", "portraits", "index.html"), encoding="utf-8") as f:
            text = f.read()
        # 85 mm on 1.5x is 56.7 mm: the 56 mm lens; on 2x exactly the 42.5 mm lens.
        self.assertIn("On APS-C, 56 mm frames about the same, and on Micro Four Thirds, 42.5 mm.", text)
        # 56 mm on Canon's 1.6x frames like 89.6 mm, so the table says so.
        self.assertIn("<td>56 mm<br><span class=\"muted\">frames like 90 mm</span></td>", text)

    def test_guides_are_linked(self):
        with open(os.path.join(ROOT, "guides", "index.html"), encoding="utf-8") as f:
            hub = f.read()
        for pair in build.COMPARISONS:
            self.assertIn('href="../%s"' % build.compare_path(pair), hub)
        for guide in build.GUIDES:
            self.assertIn('href="../%s"' % build.guide_path(guide), hub)
        for page, home in [("index.html", ""), ("lens-compare/index.html", "../"),
                           ("cameras/sony-a7-iv/index.html", "../../")]:
            with open(os.path.join(ROOT, page), encoding="utf-8") as f:
                text = f.read()
            with self.subTest(page=page):
                self.assertIn('href="%scompare/35mm-vs-50mm/"' % home, text)
                self.assertIn('href="%sguides/"' % home, text)
        with open(os.path.join(ROOT, "llms.txt"), encoding="utf-8") as f:
            llms = f.read()
        self.assertIn("## Guides", llms)
        for path in [build.compare_path(p) for p in build.COMPARISONS] + [build.guide_path(g) for g in build.GUIDES]:
            self.assertIn("(%s/%s): " % (build.BASE_URL, path), llms)

    def test_not_found_page(self):
        with open(os.path.join(ROOT, "404.html"), encoding="utf-8") as f:
            text = f.read()
        parser = Links()
        parser.feed(text)
        self.assertIn('<meta name="robots" content="noindex">', text)
        self.assertIsNone(parser.canonical)
        self.assertEqual(parser.hreflangs, [])
        # Served at any path, so every local link starts at the site root.
        for href in parser.hrefs:
            if re.match(r"^(https?:|mailto:|#)", href):
                continue
            self.assertTrue(href.startswith("/"), href)
            target = os.path.join(ROOT, href.split("?")[0].lstrip("/"))
            if target.endswith("/"):
                target = os.path.join(target, "index.html")
            self.assertTrue(os.path.exists(target), "broken link %s" % href)
        for href in ["/", "/lens-compare/", "/cameras/", "/guides/"]:
            self.assertIn('<a href="%s">' % href, text)

    def test_icons_and_logo_on_every_page(self):
        """Favicon, Apple touch icon and the header logo, resolved from each page's own depth."""
        for path in pages() + [os.path.join(ROOT, "404.html"), os.path.join(ROOT, "support.html"),
                               os.path.join(ROOT, "privacy.html"), os.path.join(ROOT, "terms.html")]:
            with open(path, encoding="utf-8") as f:
                text = f.read()
            rel = os.path.relpath(path, ROOT)
            with self.subTest(page=rel):
                for href in re.findall(r'<link rel="(?:icon|apple-touch-icon)"[^>]* href="([^"]+)"', text) + [
                        m for m in re.findall(r'<a class="brand"[^>]*><img src="([^"]+)"', text)]:
                    target = os.path.join(ROOT, href.lstrip("/")) if href.startswith("/") \
                        else os.path.normpath(os.path.join(os.path.dirname(path), href))
                    self.assertTrue(os.path.exists(target), "missing icon %s" % href)
                self.assertRegex(text, r'<link rel="icon" href="[./]*favicon\.ico"')
                self.assertRegex(text, r'<link rel="apple-touch-icon" href="[./]*assets/apple-touch-icon\.png"')
                if rel not in ("support.html", "privacy.html", "terms.html"):
                    self.assertRegex(text, r'<a class="brand" href="[^"]*"><img src="[./]*assets/icon-192\.png" width="28" height="28" alt="">Prospekt</a>')
                if '"@id": "%s"' % build.APP_ENTITY_ID in text:
                    self.assertIn('"image": "%s"' % build.APP_ICON_URL, text)

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

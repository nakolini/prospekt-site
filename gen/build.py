"""Builds the static site from data/, i18n/ and the templates below.

Usage: python3 gen/build.py   (or `make build`)

English is served at the root, every other language under /<lang>/.
A language is built when i18n/<code>.json exists. Every link is relative,
so the output works under any host or sub-path; only canonical URLs,
hreflang, the sitemap and robots.txt use BASE_URL.
"""

import hashlib
import html
import json
import math
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lensmath as lm  # noqa: E402

# The canonical host (custom domain on GitHub Pages, see CNAME).
BASE_URL = "https://prospekt.nakolini.com"

APP_ID = "6760914468"
# App Store Connect provider token (the pt= value of a campaign link).
# Without it the App Store ignores ct= in Analytics.
PROVIDER_TOKEN = ""
INDEXNOW_KEY = "ff5e02c36fce19d7d6baf4c02a9d5e1e"
PRICE = "$3.99"
# Bump when the pages change meaningfully: sitemap lastmod, JSON-LD dateModified and the footer.
SITE_UPDATED = "2026-10-10"
THREADS_URL = "https://www.threads.net/@dmytro.builds"
ANONIMO_URL = "https://apps.apple.com/app/id6762560095"
EXPENNY_URL = "https://apps.apple.com/app/id6758223013"

# Sample photos for the tool, each credited in the footer of pages that show it.
SAMPLES = [
    {"src": "assets/sample-14mm.jpg", "small": "assets/sample-14mm-1200.jpg", "small_width": 1200, "thumb": "assets/sample-14mm-thumb.jpg", "width": 1920, "height": 1280,
     "focal": 14.0, "label_key": "tool.photo_sample", "credit_key": "footer.photo_credit"},
    # Canon EOS R5 at 10 mm, trimmed from 8192 to 8013 px wide on Commons: 10 x 8192 / 8013.
    {"src": "assets/sample-10mm.jpg", "small": None, "thumb": "assets/sample-10mm-thumb.jpg", "width": 1920, "height": 1280,
     "focal": 10.2, "label_key": "tool.photo_sample_10", "credit_key": "footer.photo_credit_10"},
    # Canon EOS 5D Mark IV at 20 mm, full 6720 x 4480 frame.
    {"src": "assets/sample-20mm.jpg", "small": None, "thumb": "assets/sample-20mm-thumb.jpg", "width": 1920, "height": 1280,
     "focal": 20.0, "label_key": "tool.photo_sample_20", "credit_key": "footer.photo_credit_20"},
]
SAMPLE = SAMPLES[0]

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
with open(os.path.join(ROOT, "data", "store.json"), encoding="utf-8") as _f:
    STORE = json.load(_f)

# (code for hreflang and <html lang>, URL segment, name in that language)
LANGUAGES = [
    ("en", "", "English"),
    ("ar", "ar", "العربية"),
    ("de", "de", "Deutsch"),
    ("es", "es", "Español"),
    ("fr", "fr", "Français"),
    ("it", "it", "Italiano"),
    ("ja", "ja", "日本語"),
    ("ko", "ko", "한국어"),
    ("nl", "nl", "Nederlands"),
    ("pl", "pl", "Polski"),
    ("pt-BR", "pt-br", "Português (Brasil)"),
    ("tr", "tr", "Türkçe"),
    ("uk", "uk", "Українська"),
    ("zh-Hans", "zh-hans", "简体中文"),
    ("zh-Hant", "zh-hant", "繁體中文"),
]
RTL = {"ar"}
# Numbers with a unit inside translated sentences ("50 mm", "1.8 m", "1.4x", "f/1.4"),
# isolated on right-to-left pages like the generated ones.
MEASURE = re.compile(r"(?<!\w)(?:f/)?\d+(?:[.,]\d+)?(?:\s?(?:mm|m|ft|x|°)(?!\w))?(?:\s?(?:-|to)\s?\d+(?:\s?mm)?)?")
DECIMAL_COMMA = {"de", "es", "fr", "it", "nl", "pl", "pt-BR", "tr", "uk"}

# Generated paths, removed before each build so stale pages never linger.
GENERATED_DIRS = ["lens-compare", "cameras", "changelog", "compare", "focal-length", "guides"] + [
    s for _, s, _ in LANGUAGES if s]
GENERATED_FILES = ["index.html", "404.html", "sitemap.xml", "robots.txt", "llms.txt", ".nojekyll", "CNAME",
                   INDEXNOW_KEY + ".txt"]

CHANGELOG = [
    ("1.3.2", "date.oct_3", ["changelog.v1_3_2_1", "changelog.v1_3_2_2"]),
    ("1.3.1", "date.apr_27", ["changelog.v1_3_1_1"]),
    ("1.3", "date.month_4", ["changelog.v1_3_1"]),
    ("1.2", "date.month_4", ["changelog.v1_2_1"]),
    ("1.1", "date.month_3", ["changelog.v1_1_1", "changelog.v1_1_2", "changelog.v1_1_3"]),
    ("1.0", "date.month_3", ["changelog.v1_0_1"]),
]

FORMAT_KEYS = {1.0: "format.full_frame", 1.5: "format.aps_c", 1.6: "format.aps_c_canon",
               2.0: "format.mft", 0.79: "format.medium"}
GENERIC_CROPS = [1.0, 1.5, 1.6, 2.0, 0.79]
# The sensor sizes the comparison and guide tables cover.
FORMAT_CROPS = [1.0, 1.5, 1.6, 2.0]

# Prime pairs with a page at /compare/<a>mm-vs-<b>mm/: how many "which to choose"
# lines each has in i18n (compare.<a>_<b>_choose_<n>), and the guides it links to.
COMPARISONS = [
    {"a": 24, "b": 35, "choose": 4, "guides": ["landscape", "interiors", "travel"]},
    {"a": 28, "b": 35, "choose": 4, "guides": ["street", "travel"]},
    {"a": 35, "b": 50, "choose": 4, "guides": ["street", "travel", "portraits"]},
    {"a": 50, "b": 85, "choose": 4, "guides": ["portraits"]},
    {"a": 85, "b": 135, "choose": 4, "guides": ["portraits", "sports-wildlife"]},
]
# Use-case guides at /focal-length/<slug>/, with their full-frame recommendations,
# the main answer first. Each recommendation has a guide.<slug>_use_<focal> string.
GUIDES = [
    {"slug": "portraits", "recs": [85, 50, 135, 35], "portraits": True},
    {"slug": "street", "recs": [35, 28, 50]},
    {"slug": "landscape", "recs": [24, 16, 35, 70]},
    {"slug": "travel", "recs": [35, 24, 50]},
    {"slug": "interiors", "recs": [16, 24, 14, 35]},
    # Past the app's 300 mm, so its line mentions the 2x extender.
    {"slug": "sports-wildlife", "recs": [400, 300, 600, 200], "app_key": "app.line_guide_long"},
]
# Focal lengths the guide strings can quote numbers for (guide_values).
GUIDE_FOCALS = sorted(set(lm.TABLE_FOCAL_LENGTHS + [10, 105, 400, 600]))


def e(text):
    return html.escape(str(text), quote=True)


def asset_url(path):
    """An asset's path with a hash of its content, so a deploy never pairs new pages with cached old CSS or JS."""
    with open(os.path.join(ROOT, path), "rb") as f:
        return "%s?v=%s" % (path, hashlib.sha256(f.read()).hexdigest()[:10])


def srcset(sample, root):
    """The 1200 px copy of a sample photo for phones, where it has one."""
    if not sample["small"]:
        return ""
    return "%s%s %dw, %s%s %dw" % (root, sample["small"], sample["small_width"], root, sample["src"], sample["width"])


def app_store_url(campaign):
    query = "ct=%s&mt=8" % campaign
    if PROVIDER_TOKEN:
        query = "pt=%s&%s" % (PROVIDER_TOKEN, query)
    return "https://apps.apple.com/app/apple-store/id%s?%s" % (APP_ID, query)


class Lang:
    def __init__(self, code, segment, name, strings, fallback):
        self.code = code
        self.segment = segment
        self.name = name
        self.strings = strings
        self.fallback = fallback
        self.dir = "rtl" if code in RTL else "ltr"
        # App Store name, price and version in this language's storefront (scripts/store_info.py).
        self.store = STORE.get(code, STORE["en"])

    @property
    def prefix(self):
        return self.segment + "/" if self.segment else ""

    def t(self, key, **values):
        """A translated string with {placeholders} filled, HTML-escaped."""
        return e(self.raw(key, **values))

    def with_app(self, key, campaign, **values):
        """A translated string whose {app} placeholder becomes a link to Prospekt on the App Store."""
        text = self.t(key, app="\x00", **values)
        return text.replace("\x00", '<a href="%s">Prospekt</a>' % e(app_store_url(campaign)))

    def raw(self, key, **values):
        template = self.strings.get(key, self.fallback.get(key))
        if template is None:
            raise KeyError(key)
        values.setdefault("price", self.store["price"])
        values.setdefault("store_name", self.store["name"])
        if self.dir == "rtl":
            template = MEASURE.sub(lambda m: self.isolate(m.group(0)), template)
        return template.format(**values)

    def num(self, value, decimals=1):
        # Python 3.10+ has a correctly rounded math.hypot, so a value such as
        # 22.5 / 50 can land a hair either side of 0.45 depending on the
        # version. Rounding to 9 places first gives the same text on all of them.
        text = "%.*f" % (decimals, round(value, 9))
        return text.replace(".", ",") if self.code in DECIMAL_COMMA else text

    def isolate(self, text):
        """Keeps "24 mm" from turning into "mm 24" on right-to-left pages."""
        return "\u2066%s\u2069" % text if self.dir == "rtl" else text

    def mm(self, value):
        return self.isolate("%d mm" % round(value))

    def focal(self, value):
        """A lens you can buy: whole millimetres, or one decimal for lenses such as 42.5 mm."""
        if value != round(value) and math.isclose(value * 2, round(value * 2)):
            return self.isolate(self.num(value) + " mm")
        return self.mm(value)

    def deg(self, value):
        return self.isolate(self.num(value) + "°")

    # Lengths keep a no-break space before the unit so "3.1 m" never wraps.
    def metres(self, value, decimals=1):
        """A distance for prose and tables, in metres."""
        return self.isolate(self.num(value, decimals) + "\u00a0m")

    def metres_feet(self, value):
        """A distance with feet after it, for readers who think in feet."""
        feet = value / lm.FOOT_M
        return self.isolate("%s\u00a0m (%s\u00a0ft)" % (self.num(value), self.num(feet, 1 if feet < 10 else 0)))

    def size(self, width, height):
        """Width x height of a scene in metres."""
        return self.isolate("%s\u00a0\u00d7 %s\u00a0m" % (self.num(width), self.num(height)))

    def crop(self, crop):
        text = ("%.2f" % crop).rstrip("0").rstrip(".")
        return self.isolate((text.replace(".", ",") if self.code in DECIMAL_COMMA else text) + "x")

    def format_name(self, crop):
        return self.raw(FORMAT_KEYS[crop])


def load_languages():
    with open(os.path.join(ROOT, "i18n", "en.json"), encoding="utf-8") as f:
        english = json.load(f)
    langs = []
    for code, segment, name in LANGUAGES:
        path = os.path.join(ROOT, "i18n", "%s.json" % code)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            strings = json.load(f)
        langs.append(Lang(code, segment, name, strings, english))
    return langs


def load_bodies():
    with open(os.path.join(ROOT, "data", "bodies.json"), encoding="utf-8") as f:
        bodies = json.load(f)
    with open(os.path.join(ROOT, "data", "mounts.json"), encoding="utf-8") as f:
        mounts = json.load(f)
    for body in bodies:
        if body["slug"] not in mounts:
            raise KeyError("data/mounts.json has no entry for %s" % body["slug"])
        body.update(mounts[body["slug"]])
        body["display"] = "%s %s" % (body["brand"], body["name"])
    return bodies


# ---------------------------------------------------------------- figures

def photo_frames_svg(focals, crop, label_mm=True):
    """Frames over the sample photo, in a viewBox matching the photo."""
    w, h = 1000.0, 1000.0 * SAMPLE["height"] / SAMPLE["width"]
    aspect = SAMPLE["width"] / SAMPLE["height"]
    parts = ['<svg class="frames" viewBox="0 0 %d %d" aria-hidden="true" focusable="false">' % (w, h)]
    drawn = 0
    for focal in focals:
        fw, fh = lm.frame_in_photo(focal, crop, SAMPLE["focal"], aspect)
        if fw > 1 or fh > 1:
            continue
        x, y = (1 - fw) * w / 2, (1 - fh) * h / 2
        parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f"/>' % (x, y, fw * w, fh * h))
        if label_mm:
            # Alternate corners so labels of neighbouring frames don't overlap.
            if drawn % 2 == 0:
                parts.append('<text x="%.1f" y="%.1f">%d mm</text>' % (x + 8, y + 26, focal))
            else:
                parts.append('<text x="%.1f" y="%.1f" text-anchor="end">%d mm</text>' % (
                    x + fw * w - 8, y + fh * h - 10, focal))
        drawn += 1
    parts.append("</svg>")
    return "".join(parts)


def nested_frames_svg(crop, focals=lm.FRAME_FOCAL_LENGTHS):
    aw, ah = lm.sensor_aspect(crop)
    w, h = 600.0, 600.0 * ah / aw
    widest = focals[0]
    parts = ['<svg class="nested" viewBox="-4 -4 %d %d" role="img">' % (w + 8, h + 8)]
    for focal in focals:
        s = widest / float(focal)
        x, y = (1 - s) * w / 2, (1 - s) * h / 2
        parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f"/>' % (x, y, s * w, s * h))
        size = max(11, 22 * s ** 0.5)
        parts.append('<text x="%.1f" y="%.1f" font-size="%.0f">%d mm</text>' % (x + 6, y + size + 2, size, focal))
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------- layout

class Page:
    def __init__(self, path, title_key, description, body, jsonld=None, title_values=None,
                 extra_head="", scripts="", noindex=False, root=None):
        self.path = path  # "", "lens-compare/", "cameras/canon-r7/"
        self.title_key = title_key
        self.title_values = title_values or {}
        self.description = description
        self.body = body
        self.jsonld = jsonld or []
        self.extra_head = extra_head
        self.scripts = scripts
        # The 404 page: no canonical or alternates, kept out of search, and
        # root-absolute links because GitHub Pages serves it at any path.
        self.noindex = noindex
        self.root = root


def url_for(lang, path):
    return "%s/%s%s" % (BASE_URL, lang.prefix, path)


def rel_root(lang, path):
    depth = (lang.prefix + path).count("/")
    return "../" * depth


def header(lang, root, path):
    home = root + lang.prefix
    switch = "".join(
        '<li><a href="%s%s%s" hreflang="%s" lang="%s"%s>%s</a></li>' % (
            root, other.prefix, path, other.code, other.code,
            ' aria-current="true"' if other.code == lang.code else "", e(other.name))
        for other in ALL_LANGS)
    return """<a class="skip" href="#main">{skip}</a>
<header class="site-header"><div class="wrap bar">
<a class="brand" href="{home}"><img src="{root}assets/icon-192.png" width="28" height="28" alt="">Prospekt</a>
<nav aria-label="Prospekt"><a href="{home}lens-compare/">{tool}</a><a href="{home}cameras/">{cameras}</a><a class="nav-app" href="{app}">{get}</a></nav>
<details class="lang"><summary>{langlabel}: {langname}</summary><ul>{switch}</ul></details>
</div></header>""".format(
        skip=lang.t("nav.skip"), home=home, root=root, tool=lang.t("nav.tool"), cameras=lang.t("nav.cameras"),
        app=e(app_store_url("web_nav")), get=lang.t("nav.get_app"), langlabel=lang.t("nav.language"),
        langname=e(lang.name), switch=switch)


def footer(lang, root, credit_keys):
    home = root + lang.prefix
    credit = "".join('<p class="credit">%s</p>' % lang.t(k) for k in credit_keys)
    return """<footer class="site-footer"><div class="wrap">
<p>{made} <a href="{threads}" rel="me">Threads</a></p>
<p>{also} <a href="{anonimo}">{anonimo_t}</a> · <a href="{expenny}">{expenny_t}</a></p>
<p><a href="{home}guides/">{guides}</a> · <a href="{home}changelog/">{changelog}</a> · <a href="{root}support.html">{support}</a> · <a href="{root}privacy.html">{privacy}</a> · <a href="{root}terms.html">{terms}</a></p>
<p>{updated}</p>
{credit}
</div></footer>""".format(
        made=lang.t("footer.made_by"), threads=THREADS_URL, also=lang.t("footer.also"),
        anonimo=e(ANONIMO_URL + "?ct=web_prospekt&mt=8"), anonimo_t=lang.t("footer.anonimo"),
        expenny=e(EXPENNY_URL + "?ct=web_prospekt&mt=8"), expenny_t=lang.t("footer.expenny"),
        home=home, root=root, guides=lang.t("nav.guides"), changelog=lang.t("nav.changelog"), support=lang.t("footer.support"),
        privacy=lang.t("footer.privacy"), terms=lang.t("footer.terms"), credit=credit,
        updated=lang.t("footer.updated", date=SITE_UPDATED, version=lang.store["version"]))


def render(lang, page):
    root = rel_root(lang, page.path) if page.root is None else page.root
    title = lang.t(page.title_key, **page.title_values)
    canonical = url_for(lang, page.path)
    alternates = "".join(
        '<link rel="alternate" hreflang="%s" href="%s">\n' % (other.code, e(url_for(other, page.path)))
        for other in ALL_LANGS)
    alternates += '<link rel="alternate" hreflang="x-default" href="%s">\n' % e(url_for(ALL_LANGS[0], page.path))
    links = """<link rel="canonical" href="{canonical}">
{alternates}<meta property="og:type" content="website">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{og_image}">
<meta name="twitter:card" content="summary_large_image">
""".format(canonical=e(canonical), alternates=alternates, title=title, description=e(page.description),
           og_image=e(BASE_URL + "/" + SAMPLE["small"]))
    if page.noindex:
        links = '<meta name="robots" content="noindex">\n'
    jsonld = "".join(
        '<script type="application/ld+json">%s</script>\n' % json.dumps(block, ensure_ascii=False).replace("</", "<\\/")
        for block in page.jsonld)
    # Credit every sample photo the page shows or offers.
    credits = [s["credit_key"] for s in SAMPLES
               if s["src"] in page.body or (s["small"] and s["small"] in page.body)]
    return """<!doctype html>
<html lang="{code}" dir="{dir}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
{links}<meta name="theme-color" content="#1a1a1a">
<meta name="apple-itunes-app" content="app-id={app_id}">
<link rel="icon" href="{root}favicon.ico" sizes="16x16 32x32 48x48">
<link rel="icon" type="image/png" sizes="192x192" href="{root}assets/icon-192.png">
<link rel="apple-touch-icon" href="{root}assets/apple-touch-icon.png">
<link rel="stylesheet" href="{root}{css}">
{extra_head}{jsonld}</head>
<body>
{header}
<main id="main" class="wrap">
{body}
</main>
{footer}
{scripts}</body>
</html>
""".format(
        code=lang.code, dir=lang.dir, title=title, description=e(page.description), links=links,
        app_id=APP_ID, root=root, css=asset_url("assets/site.css"), extra_head=page.extra_head, jsonld=jsonld,
        header=header(lang, root, page.path), body=page.body.replace("{root}", root),
        footer=footer(lang, root, credits), scripts=page.scripts.replace("{root}", root).replace("{js}", asset_url("assets/lens-compare.js")))


def cta_box(lang, campaign):
    return """<aside class="cta-box">
<h2>{title}</h2>
<p>{text}</p>
<p><a class="button" href="{url}">{button}</a></p>
</aside>""".format(title=lang.t("cta.box_title"), text=lang.t("cta.box_text"),
                   url=e(app_store_url(campaign)), button=lang.t("cta.app_store"))


def faq_html(lang, items):
    return "".join("<h3>%s</h3>\n<p>%s</p>\n" % (q, a) for q, a in items)


def faq_jsonld(items):
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": html.unescape(q),
             "acceptedAnswer": {"@type": "Answer", "text": html.unescape(a)}}
            for q, a in items
        ],
    }


def breadcrumbs_jsonld(lang, crumbs):
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": html.unescape(name), "item": url_for(lang, path)}
            for i, (name, path) in enumerate(crumbs)
        ],
    }


def organization_jsonld():
    return {
        "@type": "Organization",
        "name": "nakolini",
        "url": BASE_URL + "/",
        "founder": [{"@type": "Person", "name": "Vitalii Kikot"},
                    {"@type": "Person", "name": "Dmytro Hryb"}],
        "sameAs": [THREADS_URL],
    }


# One identity for the app on every page, so a page about lenses is tied to Prospekt.
APP_ENTITY_ID = BASE_URL + "/#app"
APP_ICON_URL = BASE_URL + "/assets/icon-512.png"


def app_ref_jsonld(lang):
    return {
        "@type": "MobileApplication",
        "@id": APP_ENTITY_ID,
        "name": "Prospekt",
        "description": lang.raw("home.description"),
        "operatingSystem": "iOS 17.0 or later",
        "applicationCategory": "PhotographyApplication",
        "url": BASE_URL + "/",
        "image": APP_ICON_URL,
        "downloadUrl": "https://apps.apple.com/app/id%s" % APP_ID,
        "softwareVersion": STORE["en"]["version"],
        "offers": {"@type": "Offer", "price": "3.99", "priceCurrency": "USD"},
    }


def app_jsonld(lang):
    return {
        "@context": "https://schema.org",
        "@type": "MobileApplication",
        "@id": APP_ENTITY_ID,
        "name": "Prospekt",
        "alternateName": "Lens Simulator: Prospekt",
        "description": lang.raw("home.description"),
        "inLanguage": lang.code,
        "operatingSystem": "iOS 17.0 or later",
        "applicationCategory": "PhotographyApplication",
        "url": BASE_URL + "/",
        "image": APP_ICON_URL,
        "softwareVersion": STORE["en"]["version"],
        "dateModified": STORE["en"]["released"],
        "downloadUrl": "https://apps.apple.com/app/id%s" % APP_ID,
        "installUrl": "https://apps.apple.com/app/id%s" % APP_ID,
        "offers": {"@type": "Offer", "price": "3.99", "priceCurrency": "USD"},
        "publisher": organization_jsonld(),
        "author": organization_jsonld(),
        "sameAs": ["https://apps.apple.com/app/id%s" % APP_ID],
    }


# ---------------------------------------------------------------- pages

def home_page(lang):
    faq = [(lang.t("home.faq_%d_q" % i), lang.t("home.faq_%d_a" % i)) for i in range(1, 11)]
    compare_rows = [
        ("home.compare_row_live", "home.compare_yes", "home.compare_live_calc", "home.compare_yes", "home.compare_yes"),
        ("home.compare_row_body", "home.compare_body_prospekt", "home.compare_body_calc", "home.compare_body_cine", "home.compare_yes"),
        ("home.compare_row_bokeh", "home.compare_no", "home.compare_no", "home.compare_some", "home.compare_yes"),
        ("home.compare_row_cost", "home.compare_cost_prospekt", "home.compare_cost_calc", "home.compare_cost_cine", "home.compare_cost_rent"),
        ("home.compare_row_offline", "home.compare_yes", "home.compare_no", "home.compare_some", "home.compare_yes"),
    ]
    compare = "".join("<tr><th scope=\"row\">%s</th>%s</tr>" % (
        lang.t(row[0]), "".join("<td>%s</td>" % lang.t(k) for k in row[1:])) for row in compare_rows)
    body = """<section class="hero">
<h1>{h1}</h1>
<p class="lead">{lead}</p>
<p class="facts">{facts}</p>
<p class="actions"><a class="button" href="{app}">{cta}</a> <a class="button secondary" href="lens-compare/">{try_tool}</a></p>
<figure class="photo"><div class="photo-frame"><img src="{{root}}{small}" width="1200" height="800" alt="" fetchpriority="high">{frames}</div>
<figcaption>{caption}</figcaption></figure>
</section>
<section><h2>{for_title}</h2><ul class="checks">{for_items}</ul></section>
<section><h2>{how_title}</h2><ol class="steps">{how_items}</ol></section>
<section><h2>{price_title}</h2>
<table class="price"><tr><th scope="row">{price_row}</th><td><strong>{price_value}</strong></td></tr></table>
<p>{price_includes}</p><p class="muted">{price_note}</p></section>
<section><h2>{privacy_title}</h2><p>{privacy_text}</p></section>
<section><h2>{limits_title}</h2><ul>{limits}</ul></section>
<section><h2>{compare_title}</h2>
<div class="scroll"><table class="compare"><thead><tr><td></td><th scope="col">{c1}</th><th scope="col">{c2}</th><th scope="col">{c3}</th><th scope="col">{c4}</th></tr></thead><tbody>{compare}</tbody></table></div>
<p>{compare_note}</p></section>
{popular}
<section class="faq"><h2>{faq_title}</h2>{faq}</section>
{cta_box}""".format(
        h1=lang.t("home.h1"), lead=lang.t("home.lead"), facts=lang.t("home.facts"),
        app=e(app_store_url("web_home")), cta=lang.t("cta.app_store"), try_tool=lang.t("cta.try_tool"),
        small=SAMPLE["small"], frames=photo_frames_svg([24, 35, 50, 85], 1.0),
        caption=lang.t("home.hero_caption"),
        for_title=lang.t("home.for_title"),
        for_items="".join("<li>%s</li>" % lang.t("home.for_%d" % i) for i in range(1, 6)),
        how_title=lang.t("home.how_title"),
        how_items="".join("<li>%s</li>" % lang.t("home.how_%d" % i) for i in range(1, 5)),
        price_title=lang.t("home.price_title"), price_row=lang.t("home.price_row"),
        price_value=lang.t("home.price_value"), price_includes=lang.t("home.price_includes"),
        price_note=lang.t("home.price_note"), privacy_title=lang.t("home.privacy_title"),
        privacy_text=lang.t("home.privacy_text"), limits_title=lang.t("home.limits_title"),
        limits="".join("<li>%s</li>" % lang.t("home.limits_%d" % i) for i in range(1, 6)),
        compare_title=lang.t("home.compare_title"), c1=lang.t("home.compare_col_prospekt"),
        c2=lang.t("home.compare_col_calc"), c3=lang.t("home.compare_col_cine"),
        c4=lang.t("home.compare_col_rent"), compare=compare, compare_note=lang.t("home.compare_note"),
        popular=popular_section(lang, ""),
        faq_title=lang.t("home.faq_title"), faq=faq_html(lang, faq), cta_box=cta_box(lang, "web_home"))
    return Page("", "home.title", lang.raw("home.description"), body,
                jsonld=[app_jsonld(lang), faq_jsonld(faq)])


def equivalence_table(lang):
    head = "".join('<th scope="col">%s<br><span class="muted">%s</span></th>' % (
        e(lang.format_name(c)), lang.crop(c)) for c in GENERIC_CROPS[1:])
    rows = "".join("<tr><th scope=\"row\">%s</th>%s</tr>" % (
        lang.mm(eq), "".join("<td>%s</td>" % lang.mm(lm.focal_for_equivalent(eq, c)) for c in GENERIC_CROPS[1:]))
        for eq in lm.CLASSIC_EQUIVALENTS)
    return '<div class="scroll"><table class="equiv"><thead><tr><th scope="col">%s</th>%s</tr></thead><tbody>%s</tbody></table></div>' % (
        lang.t("tool.equiv_col_ff"), head, rows)


def angle_table(lang, focals, crop, link_rows=False):
    rows = []
    for focal in focals:
        h, v, d = lm.angles(focal, crop)
        rows.append('<tr data-focal="%s"><th scope="row">%s</th><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
            focal, lang.mm(focal), lang.mm(lm.equivalent(focal, crop)), lang.deg(h), lang.deg(v), lang.deg(d)))
    return """<div class="scroll"><table class="angles"><thead><tr><th scope="col">{f}</th><th scope="col">{eq}</th><th scope="col">{h}</th><th scope="col">{v}</th><th scope="col">{d}</th></tr></thead>
<tbody>{rows}</tbody></table></div>""".format(
        f=lang.t("tool.table_focal"), eq=lang.t("tool.table_equiv"), h=lang.t("tool.table_h"),
        v=lang.t("tool.table_v"), d=lang.t("tool.table_d"), rows="".join(rows))


def coverage_table(lang, crop):
    """What each lens covers at 1 to 10 m: width x height, camera horizontal."""
    head = "".join('<th scope="col">%s</th>' % lang.t("tool.at_distance", distance=lang.metres(d, 0))
                   for d in lm.COVERAGE_DISTANCES)
    rows = "".join('<tr><th scope="row">%s</th>%s</tr>' % (
        lang.mm(focal), "".join("<td>%s</td>" % lang.size(*lm.coverage(focal, crop, d))
                                for d in lm.COVERAGE_DISTANCES))
        for focal in lm.COVERAGE_FOCAL_LENGTHS)
    return ('<div class="scroll"><table class="distances"><thead><tr><th scope="col">%s</th>%s</tr></thead>'
            "<tbody>%s</tbody></table></div>") % (lang.t("tool.table_focal"), head, rows)


def portrait_distances(crop, focal):
    """Full-body and head-and-shoulders distances in metres, camera vertical."""
    return (lm.distance_to_fit(lm.FULL_BODY_M, focal, crop),
            lm.distance_to_fit(lm.HEAD_SHOULDERS_M, focal, crop))


def portrait_list(lang, crop, row_key, **values):
    items = []
    for focal in lm.PORTRAIT_FOCAL_LENGTHS:
        full, head = portrait_distances(crop, focal)
        items.append("<li>%s</li>" % lang.t(row_key, focal=lang.mm(focal), full=lang.metres_feet(full),
                                             head=lang.metres_feet(head), **values))
    return '<ul class="portraits">%s</ul>' % "".join(items)


def portrait_formats_table(lang):
    """Full-body distance, camera vertical, for each focal length on each sensor size."""
    crops = [1.0, 1.5, 1.6, 2.0]
    head = "".join('<th scope="col">%s<br><span class="muted">%s</span></th>' % (
        e(lang.format_name(c)), lang.crop(c)) for c in crops)
    rows = "".join("<tr><th scope=\"row\">%s</th>%s</tr>" % (lang.mm(f), "".join(
        "<td>%s</td>" % lang.metres_feet(portrait_distances(c, f)[0]) for c in crops))
        for f in lm.PORTRAIT_FOCAL_LENGTHS)
    return '<div class="scroll"><table class="distances"><thead><tr><th scope="col">%s</th>%s</tr></thead><tbody>%s</tbody></table></div>' % (
        lang.t("tool.table_focal"), head, rows)


def body_options(lang, bodies):
    # data-label names the camera inside parentheses ("24 mm (Full frame, 1x)") without nesting them.
    generic = "".join('<option value="generic-%s" data-crop="%s" data-label="%s, %s">%s (%s)</option>' % (
        ("%g" % c).replace(".", "_"), c, e(lang.format_name(c)), lang.crop(c), e(lang.format_name(c)), lang.crop(c))
        for c in GENERIC_CROPS)
    groups = ['<optgroup label="%s">%s</optgroup>' % (lang.t("tool.generic_group"), generic)]
    brand = None
    for body in bodies:
        if body["brand"] != brand:
            if brand is not None:
                groups.append("</optgroup>")
            brand = body["brand"]
            groups.append('<optgroup label="%s">' % e(brand))
        groups.append('<option value="%s" data-crop="%s">%s</option>' % (
            body["slug"], body["crop"], e(body["display"])))
    groups.append("</optgroup>")
    return "".join(groups)


TOOL_JS_KEYS = ["tool.too_wide", "tool.preview_title", "tool.copied", "tool.share_own", "tool.share",
                "tool.table_focal", "tool.table_equiv", "tool.table_h", "tool.table_v", "tool.table_d",
                 "tool.table_covers", "tool.table_fit", "tool.preview_hint", "tool.lens_cta",
                 "tool.distance_summary", "tool.outside_photo", "tool.use_sample", "tool.scene_note",
                 "tool.fit_body_result", "tool.fit_head_result", "tool.focal_error", "tool.zoom_error",
                 "tool.photo_error", "tool.photo_focal_missing"]

# How wide the tool's photo is drawn: beside the controls from 960 px, full width below.
PHOTO_SIZES = "(min-width: 960px) 800px, 100vw"

ZOOM_PRESETS = [(10, 18), (16, 35), (18, 55), (24, 70), (24, 105), (28, 75), (70, 200), (100, 400), (150, 600)]


def tool_page(lang, bodies):
    faq_values = {"d%d" % f: lang.metres_feet(portrait_distances(1.0, f)[0]) for f in lm.PORTRAIT_FOCAL_LENGTHS}
    faq_values.update({
        "d85_15": lang.metres_feet(portrait_distances(1.5, 85)[0]),
        "d85_16": lang.metres_feet(portrait_distances(1.6, 85)[0]),
        "d85_15_h": lang.metres_feet(lm.distance_to_fit(lm.FULL_BODY_M, 85, 1.5, vertical=False)),
        "d50_15": lang.metres_feet(portrait_distances(1.5, 50)[0]),
    })
    faq = [(lang.t("tool.faq_%d_q" % i), lang.t("tool.faq_%d_a" % i, **faq_values)) for i in range(1, 6)]
    default_focals = [24, 35, 50, 85]
    # Chips show the bare number; screen readers hear "24 mm".
    chips = "".join('<button type="button" class="chip" data-focal="%d" aria-pressed="%s" aria-label="%d mm">%d</button>' % (
        f, "true" if f in default_focals else "false", f, f) for f in lm.TABLE_FOCAL_LENGTHS)
    zoom_chips = "".join(
        '<button type="button" class="chip" data-zoom="%d-%d" aria-pressed="false" aria-label="%d-%d mm">%d-%d</button>' % (
            a, b, a, b, a, b) for a, b in ZOOM_PRESETS)
    strings = {k: lang.raw(k, focal="{focal}", distance="{distance}", height="{height}", equiv="{equiv}",
                           min="{min}", max="{max}")
               for k in TOOL_JS_KEYS}
    # The camera lists are filled in by the script, so the page's text doesn't open with 120 camera names.
    data = json.dumps({"strings": strings, "samples": SAMPLES, "lang": lang.code, "options": body_options(lang, bodies),
                       "rtl": lang.dir == "rtl",
                       "fill": lm.PORTRAIT_FILL, "foot": lm.FOOT_M, "eye": lm.EYE_LEVEL_M,
                       "head": lm.HEAD_SHOULDERS_M / lm.FULL_BODY_M},
                      ensure_ascii=False).replace("</", "<\\/")
    # Sample photos as tiles; the radio's name is the full label, the tile shows the focal length.
    samples = "".join(
        '<label class="tile"><input type="radio" name="photo" value="sample-%d"%s aria-label="%s">'
        '<img src="{root}%s" width="240" height="160" alt=""><span class="tile-text">%s</span></label>' % (
            i, " checked" if i == 0 else "", e(html.unescape(lang.t(sample["label_key"]))), sample["thumb"],
            lang.mm(sample["focal"])) for i, sample in enumerate(SAMPLES))
    # The person scene, drawn by the script (the tile too).
    samples += ('<label class="tile"><input type="radio" name="photo" value="person" aria-label="%s">'
                '<svg class="tile-scene" id="person-thumb" viewBox="0 0 1000 666.667" aria-hidden="true"></svg>'
                '<span class="tile-text">%s</span></label>' % (
                    e(html.unescape(lang.t("tool.photo_person_label"))), lang.t("tool.photo_person")))
    # The photo comes first and stays in view while the controls change it (site.css);
    # the table, notes and sharing follow.
    body = """<h1>{h1}</h1>
<p class="lead">{lead}</p>
<noscript><p class="note">{noscript}</p></noscript>
<form id="tool" class="tool" hidden>
<div class="workspace">
<div class="viewer" id="viewer">
<div class="photo-frame" id="stage"><img id="photo" src="{{root}}{src}" srcset="{srcset}" sizes="{sizes}" data-root="{{root}}" width="{w}" height="{h}" alt="">{frames}
<svg class="scene" id="scene" viewBox="0 0 1000 666.667" aria-hidden="true" hidden></svg>
<button type="button" class="lens-back" id="lens-back" hidden>{lens_back}</button></div>
<p class="legend" id="legend" hidden></p>
<div class="scene-actions" id="scene-actions" hidden><button type="button" data-fit="body"><svg class="figure" viewBox="-150 -10 300 1020" aria-hidden="true"></svg>{fit_body}</button><button type="button" data-fit="head"><svg class="figure" viewBox="-150 -10 300 290" aria-hidden="true"></svg>{fit_head}</button></div>
<p class="viewer-hint" id="viewer-hint" aria-live="polite">{preview_hint}</p>
<p class="lens-cta" id="lens-cta" hidden><a href="{lens_url}"></a></p>
<p class="notes" id="notes" aria-live="polite"></p>
</div>
<div class="panel">
<div class="group">
<label class="group-label" for="body">{body_label}</label><select id="body"></select>
<button type="button" class="link-button" id="add-body2" aria-controls="body2-box" aria-expanded="false">+ {body2_add}</button>
<div id="body2-box" hidden><label class="group-label" for="body2">{body2_label}</label><select id="body2"><option value="">{body2_none}</option></select></div>
</div>
<div class="group">
<p class="group-label" id="focals-label">{focals_label}</p>
<div class="chips scroller" id="chips" role="group" aria-labelledby="focals-label">{chips}<button type="button" class="chip more" id="more-focal" aria-controls="custom-row" aria-expanded="false" aria-label="{custom_label}">+</button></div>
<div class="inline-row" id="custom-row" hidden><label for="custom">{custom_label}</label> <input id="custom" type="number" min="4" max="1200" step="1" inputmode="numeric" aria-describedby="custom-error"> <button type="button" id="add">{add}</button>
<span class="field-error" id="custom-error" aria-live="polite"></span></div>
<p class="group-label" id="zooms-label">{zooms_label}</p>
<div class="chips scroller" id="zooms" role="group" aria-labelledby="zooms-label">{zoom_chips}<button type="button" class="chip more" id="more-zoom" aria-controls="zoom-row" aria-expanded="false" aria-label="{zoom_custom_label}">+</button></div>
<div class="inline-row" id="zoom-row" hidden><span id="zoom-custom-label">{zoom_custom_label}</span> <span class="range"><input id="zoom-from" type="number" min="4" max="1200" step="1" inputmode="numeric" aria-label="{zoom_from}" aria-describedby="zoom-error"> <span aria-hidden="true">-</span> <input id="zoom-to" type="number" min="4" max="1200" step="1" inputmode="numeric" aria-label="{zoom_to}" aria-describedby="zoom-error"></span> <button type="button" id="add-zoom" aria-describedby="zoom-custom-label">{add}</button>
<span class="field-error" id="zoom-error" aria-live="polite"></span></div>
</div>
<div class="group">
<p class="group-label" id="photo-label">{photo_label}</p>
<div class="tiles" role="radiogroup" aria-labelledby="photo-label">{samples}<label class="tile own"><input type="radio" name="photo" value="own"><span class="tile-plus" aria-hidden="true">+</span><span class="tile-text">{photo_own}</span></label></div>
<p class="field-error" id="photo-error" role="alert"></p>
<div id="own" hidden><input id="file" type="file" accept="image/*" aria-label="{photo_own}">
<label class="field">{photo_focal_label} <input id="photo-focal" type="number" min="4" max="1200" step="0.1" value="26" aria-describedby="photo-focal-note"></label>
<p class="field-note" id="photo-focal-note" aria-live="polite"></p>
<p class="muted">{photo_focal_hint} {photo_private}</p></div>
<p class="muted" id="scene-note" hidden></p>
</div>
<details class="group distance">
<summary><span class="group-label">{distance_legend}</span> <span class="summary-value" id="distance-summary"></span></summary>
<div class="field"><label for="distance">{distance_label}</label> <span class="with-unit"><input id="distance" type="number" min="0.1" max="100000" step="0.1" value="3" inputmode="decimal"> <span class="unit">m</span></span></div>
<div class="field"><label for="subject">{subject_label}</label> <span class="with-unit"><input id="subject" type="number" min="0.01" max="100000" step="0.1" value="1.8" inputmode="decimal"> <span class="unit">m</span></span></div>
<div class="segmented" role="radiogroup" aria-label="{orient_label}"><label><input type="radio" name="orient" value="v" checked> {vertical}</label><label><input type="radio" name="orient" value="h"> {horizontal}</label></div>
<div class="segmented" role="radiogroup" aria-label="{unit_label}"><label><input type="radio" name="unit" value="m" checked> {unit_m}</label><label><input type="radio" name="unit" value="ft"> {unit_ft}</label></div>
<p class="muted">{subject_hint}</p>
</details>
</div>
</div>
<div class="results" id="results-box">
<label class="switch"><input type="checkbox" id="show-angles"> {angles_toggle}</label>
<div id="results">{table}</div>
<p class="muted">{distance_note} {soft}</p>
<div class="actions"><button type="button" id="share">{share}</button> <span id="share-status" role="status"></span></div>
<p class="inline-cta"><a href="{app_url}">{cta_title} <span>{app_short} &rarr;</span></a></p>
</div>
</form>
<figure class="photo" id="static-figure"><div class="photo-frame"><img src="{{root}}{small}" width="1200" height="800" alt="" loading="lazy">{frames}</div>
<figcaption>{static_caption}</figcaption></figure>
<p class="app-line">{app_line}</p>
<section><h2>{equiv_title}</h2><p>{equiv_intro}</p>{equiv_table}</section>
<section id="distances"><h2>{distance_title}</h2><p>{distance_intro}</p>{distance_table}</section>
<section id="portraits"><h2>{portrait_title}</h2><p>{portrait_intro}</p>{portraits}
<h3>{formats_title}</h3><p>{formats_intro}</p>{formats_table}</section>
<section><h2>{math_title}</h2><ul>{math}</ul></section>
<section class="faq"><h2>{faq_title}</h2>{faq}</section>
{popular}
{cta_box}
<script type="application/json" id="tool-data">{data}</script>""".format(
        h1=lang.t("tool.h1"), lead=lang.t("tool.lead"), noscript=lang.t("tool.noscript"),
        body_label=lang.t("tool.body_label"), body2_label=lang.t("tool.body2_label"),
        body2_add=lang.t("tool.body2_add"), lens_back=lang.t("tool.lens_back"),
        fit_body=lang.t("tool.fit_body"), fit_head=lang.t("tool.fit_head"),
        angles_toggle=lang.t("tool.angles_toggle"), app_url=e(app_store_url("web_lenstool_inline")),
        lens_url=e(app_store_url("web_lensview")), app_line=lang.with_app("app.line_tool", "web_lenstool_line"),
        cta_title=lang.t("cta.box_title"), app_short=lang.t("cta.app_store_short"),
        body2_none=lang.t("tool.body2_none"),
        focals_label=lang.t("tool.focals_label"), chips=chips, custom_label=lang.t("tool.custom_label"),
        add=lang.t("tool.add"), zooms_label=lang.t("tool.zooms_label"), zoom_chips=zoom_chips,
        zoom_custom_label=lang.t("tool.zoom_custom_label"), zoom_from=lang.t("tool.zoom_from"),
        zoom_to=lang.t("tool.zoom_to"), distance_legend=lang.t("tool.distance_legend"),
        distance_label=lang.t("tool.distance_label"), unit_label=lang.t("tool.unit_label"),
        unit_m=lang.t("tool.unit_m"), unit_ft=lang.t("tool.unit_ft"), subject_label=lang.t("tool.subject_label"),
        vertical=lang.t("tool.subject_vertical"), horizontal=lang.t("tool.subject_horizontal"),
        orient_label=lang.t("tool.orient_label"),
        subject_hint=lang.t("tool.subject_hint"), photo_label=lang.t("tool.photo_label"),
        samples=samples, photo_own=lang.t("tool.photo_own"),
        photo_focal_label=lang.t("tool.photo_focal_label"), photo_focal_hint=lang.t("tool.photo_focal_hint"),
        photo_private=lang.t("tool.photo_private"), src=SAMPLE["src"], small=SAMPLE["small"],
        w=SAMPLE["width"], h=SAMPLE["height"], frames=photo_frames_svg(default_focals, 1.0),
        srcset=srcset(SAMPLE, "{root}"), sizes=PHOTO_SIZES,
        table=angle_table(lang, default_focals, 1.0), preview_hint=lang.t("tool.preview_hint"),
        distance_note=lang.t("tool.distance_note"), soft=lang.t("tool.soft_note"), share=lang.t("tool.share"),
        static_caption=lang.t("tool.static_caption"), equiv_title=lang.t("tool.equiv_title"),
        equiv_intro=lang.t("tool.equiv_intro"), equiv_table=equivalence_table(lang),
        distance_title=lang.t("tool.distance_title"), distance_intro=lang.t("tool.distance_intro"),
        distance_table=coverage_table(lang, 1.0), portrait_title=lang.t("tool.portrait_title"),
        portrait_intro=lang.t("tool.portrait_intro"), portraits=portrait_list(lang, 1.0, "tool.portrait_row"),
        formats_title=lang.t("tool.portrait_formats_title"), formats_intro=lang.t("tool.portrait_formats_intro"),
        formats_table=portrait_formats_table(lang),
        math_title=lang.t("tool.math_title"),
        math="".join("<li>%s</li>" % lang.t("tool.math_%d" % i) for i in range(1, 6)),
        faq_title=lang.t("home.faq_title"), faq=faq_html(lang, faq), popular=popular_section(lang, "../"),
        cta_box=cta_box(lang, "web_lenstool"), data=data)
    app = {
        "@context": "https://schema.org",
        "@type": "WebApplication",
        "name": html.unescape(lang.t("tool.h1")),
        "url": url_for(lang, "lens-compare/"),
        "inLanguage": lang.code,
        "applicationCategory": "PhotographyApplication",
        "browserRequirements": "Requires JavaScript",
        "operatingSystem": "Any",
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
        "publisher": organization_jsonld(),
        "mentions": app_ref_jsonld(lang),
    }
    crumbs = breadcrumbs_jsonld(lang, [("Prospekt", ""), (lang.t("nav.tool"), "lens-compare/")])
    return Page("lens-compare/", "tool.title", lang.raw("tool.description"), body,
                jsonld=[app, faq_jsonld(faq), crumbs],
                # The "js" class hides the no-script figure before it starts loading its photo.
                extra_head='<script>document.documentElement.className += " js";</script>\n',
                scripts='<script src="{root}{js}" defer></script>\n')


def cameras_page(lang, bodies):
    rows = []
    for body in bodies:
        rows.append('<tr><th scope="row"><a href="%s/">%s</a></th><td>%s</td><td>%s</td></tr>' % (
            body["slug"], e(body["display"]), e(lang.format_name(body["crop"])), lang.crop(body["crop"])))
    body = """<h1>{h1}</h1>
<p class="lead">{lead}</p>
<div class="scroll"><table class="cameras"><thead><tr><th scope="col">{camera}</th><th scope="col">{format}</th><th scope="col">{crop}</th></tr></thead>
<tbody>{rows}</tbody></table></div>
{cta_box}""".format(h1=lang.t("cameras.h1"), lead=lang.t("cameras.lead"), camera=lang.t("tool.body_label"),
                     format=lang.t("cameras.format_col"), crop=lang.t("cameras.crop_col"), rows="".join(rows),
                     cta_box=cta_box(lang, "web_body"))
    crumbs = breadcrumbs_jsonld(lang, [("Prospekt", ""), (lang.t("nav.cameras"), "cameras/")])
    return Page("cameras/", "cameras.title", lang.raw("cameras.description"), body, jsonld=[crumbs])


def body_page(lang, body, bodies):
    crop = body["crop"]
    name = body["display"]
    h50 = lm.angles(50, crop)[0]
    values = {
        "body": name, "crop": lang.crop(crop), "format": lang.format_name(crop),
        "equiv_50": lang.mm(lm.equivalent(50, crop)), "h_50": lang.deg(h50),
        "focal_for_50": lang.mm(lm.focal_for_equivalent(50, crop)),
        "full_85": lang.metres_feet(portrait_distances(crop, 85)[0]),
        "head_85": lang.metres_feet(portrait_distances(crop, 85)[1]),
        "cover_35_3": lang.size(*lm.coverage(35, crop, 3)),
        "cover_35_10": lang.size(*lm.coverage(35, crop, 10)),
        "equiv_35": lang.mm(lm.equivalent(35, crop)),
        "cover_50_3": lang.size(*lm.coverage(50, crop, 3)),
        "focal_for_35": lang.mm(lm.focal_for_equivalent(35, crop)),
    }
    full_frame = math.isclose(crop, 1.0)
    if math.isclose(crop, 1.0):
        intro = lang.t("body.intro_ff", **values)
    else:
        intro = lang.t("body.intro", **values)
    mount = "<p>%s</p>" % lang.t("body.mount", mount=body["mount"]) if body.get("mount") else ""
    note = "<p class=\"note\">%s</p>" % lang.t(body["note_key"]) if body.get("note_key") else ""
    # On full frame every lens is its own equivalent, so the list would only repeat itself.
    classic = "" if full_frame else '<section><h2>%s</h2><p>%s</p><ul>%s</ul></section>' % (
        lang.t("body.classic_title", **values), lang.t("body.classic_intro", **values),
        "".join("<li>%s</li>" % lang.t("body.classic_row", equiv=lang.mm(eq), body=name,
                                        focal=lang.mm(lm.focal_for_equivalent(eq, crop)))
                for eq in lm.CLASSIC_EQUIVALENTS))
    # Zoom ranges common for this sensor size; fixed-lens cameras have none.
    zooms = "" if body.get("note_key") else '<section id="zooms"><h2>%s</h2><ul>%s</ul></section>' % (
        lang.t("body.zoom_title", **values), "".join(
            "<li>%s</li>" % lang.t("body.zoom_row_ff" if full_frame else "body.zoom_row", body=name,
                                   zoom=lang.isolate("%d-%d mm" % (a, b)),
                                   equiv=lang.isolate("%d-%d mm" % (round(a * crop), round(b * crop))),
                                   wide=lang.deg(lm.angles(a, crop)[0]), tele=lang.deg(lm.angles(b, crop)[0]))
            for a, b in lm.COMMON_ZOOMS[lm.format_key(crop)]))
    same = [b for b in bodies if math.isclose(b["crop"], crop) and b["slug"] != body["slug"]]
    same_html = ", ".join('<a href="../%s/">%s</a>' % (b["slug"], e(b["display"])) for b in same)
    # The app question stays last.
    # Which lens gives a 50 mm look is a non-question on full frame; the app question stays last.
    order = [1, 6, 4, 5, 3] if full_frame else [1, 2, 6, 4, 5, 3]
    faq = [(lang.t("body.faq_%d_q" % i, **values),
            lang.t("body.faq_6_a_ff" if (i == 6 and full_frame) else "body.faq_%d_a" % i, **values)) for i in order]
    page_body = """<p class="crumbs"><a href="../">{cameras}</a></p>
<h1>{h1}</h1>
<p class="lead">{intro}</p>
{mount}{note}
<p class="app-line">{app_line}</p>
<p><a class="button secondary" href="../../lens-compare/?body={slug}">{open_tool}</a></p>
<section><h2>{frames_title}</h2>
<figure class="nested-figure">{svg}<figcaption>{frames_caption}</figcaption></figure></section>
<section><h2>{table_title}</h2>{table}</section>
{classic}
{zooms}
<section id="distances"><h2>{distance_title}</h2><p>{distance_intro}</p>{distance_table}</section>
<section id="portraits"><h2>{portrait_title}</h2><p>{portrait_intro}</p>{portraits}</section>
<section><h2>{compare_title}</h2><ul class="links cols">{compare}<li><a href="../../guides/">{all_guides}</a></li></ul></section>
<section class="faq"><h2>{faq_title}</h2>{faq}</section>
{cta_box}
<section><h2>{same_title}</h2><p>{same}</p></section>""".format(
        cameras=lang.t("nav.cameras"), h1=lang.t("body.h1", **values), intro=intro, mount=mount, note=note,
        app_line=lang.with_app("app.line_body", "web_body_line", **values),
        slug=body["slug"], open_tool=lang.t("body.open_tool", **values),
        frames_title=lang.t("body.frames_title", **values),
        svg=nested_frames_svg(crop), frames_caption=lang.t("body.frames_caption", **values),
        table_title=lang.t("body.table_title", **values), table=angle_table(lang, lm.TABLE_FOCAL_LENGTHS, crop),
        classic=classic, zooms=zooms, distance_title=lang.t("body.distance_title", **values),
        distance_intro=lang.t("body.distance_intro", **values), distance_table=coverage_table(lang, crop),
        portrait_title=lang.t("body.portrait_title", **values),
        portrait_intro=lang.t("body.portrait_intro", **values),
        portraits=portrait_list(lang, crop, "body.portrait_row", body=name),
        compare_title=lang.t("guides.compare_title"), compare=compare_links(lang, "../../"),
        all_guides=lang.t("guides.all"),
        faq_title=lang.t("home.faq_title"), faq=faq_html(lang, faq),
        cta_box=cta_box(lang, "web_body"), same_title=lang.t("body.same_format"), same=same_html)
    path = "cameras/%s/" % body["slug"]
    crumbs = breadcrumbs_jsonld(lang, [("Prospekt", ""), (lang.t("nav.cameras"), "cameras/"), (name, path)])
    page_ld = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": lang.raw("body.title", **values),
        "url": url_for(lang, path),
        "inLanguage": lang.code,
        "about": {"@type": "Thing", "name": name},
        "dateModified": SITE_UPDATED,
        "mentions": app_ref_jsonld(lang),
        "publisher": organization_jsonld(),
    }
    return Page(path, "body.title", lang.raw("body.description", **values), page_body,
                jsonld=[page_ld, faq_jsonld(faq), crumbs], title_values=values)


def changelog_page(lang):
    entries = "".join("<section><h2>%s <span class=\"muted\">%s</span></h2><ul>%s</ul></section>" % (
        e(version), lang.t(date), "".join("<li>%s</li>" % lang.t(k) for k in keys))
        for version, date, keys in CHANGELOG)
    body = "<h1>%s</h1>\n<p class=\"lead\">%s</p>\n%s\n%s" % (
        lang.t("changelog.h1"), lang.t("changelog.lead"), entries, cta_box(lang, "web_changelog"))
    return Page("changelog/", "changelog.title", lang.raw("changelog.description"), body)


# ---------------------------------------------------------------- guides

def compare_path(pair):
    return "compare/%dmm-vs-%dmm/" % (pair["a"], pair["b"])


def compare_key(pair):
    return "compare.%d_%d" % (pair["a"], pair["b"])


def guide_path(guide):
    return "focal-length/%s/" % guide["slug"]


def guide_key(guide):
    return "guide.%s" % guide["slug"].replace("-", "_")


GUIDES_BY_SLUG = {g["slug"]: g for g in GUIDES}


def compare_links(lang, home, pairs=None):
    return "".join('<li><a href="%s%s">%s</a></li>' % (
        home, compare_path(p), lang.t("compare.link", a=lang.mm(p["a"]), b=lang.mm(p["b"])))
        for p in (COMPARISONS if pairs is None else pairs))


def guide_links(lang, home, guides=None):
    return "".join('<li><a href="%s%s">%s</a></li>' % (home, guide_path(g), lang.t(guide_key(g) + "_name"))
                   for g in (GUIDES if guides is None else guides))


def popular_section(lang, home):
    """Every guide and comparison, for the home and tool pages."""
    return '<section><h2>%s</h2><ul class="links cols">%s%s<li><a href="%sguides/">%s</a></li></ul></section>' % (
        lang.t("guides.popular_title"), guide_links(lang, home), compare_links(lang, home), home,
        lang.t("guides.all"))


def webpage_jsonld(lang, path, name, about):
    return {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": html.unescape(name),
        "url": url_for(lang, path),
        "inLanguage": lang.code,
        "about": [{"@type": "Thing", "name": html.unescape(a)} for a in about],
        "dateModified": SITE_UPDATED,
        "mentions": app_ref_jsonld(lang),
        "publisher": organization_jsonld(),
    }


def compare_values(lang, pair):
    a, b = pair["a"], pair["b"]
    return {
        "a": lang.mm(a), "b": lang.mm(b),
        "h_a": lang.deg(lm.angles(a, 1.0)[0]), "h_b": lang.deg(lm.angles(b, 1.0)[0]),
        "cover_a": lang.size(*lm.coverage(a, 1.0, 3)), "cover_b": lang.size(*lm.coverage(b, 1.0, 3)),
        # How much bigger the longer lens draws the same subject from the same spot.
        "ratio": lang.crop(round(b / float(a), 2)),
        "full_a": lang.metres_feet(portrait_distances(1.0, a)[0]),
        "full_b": lang.metres_feet(portrait_distances(1.0, b)[0]),
        "full_a_15": lang.metres_feet(portrait_distances(1.5, a)[0]),
        "full_b_15": lang.metres_feet(portrait_distances(1.5, b)[0]),
        "eq_a": lang.mm(lm.equivalent(a, 1.5)), "eq_b": lang.mm(lm.equivalent(b, 1.5)),
        "eq_a_16": lang.mm(lm.equivalent(a, 1.6)), "eq_b_16": lang.mm(lm.equivalent(b, 1.6)),
        "ff_a": lang.focal(lm.real_focal(a, 1.5)), "ff_b": lang.focal(lm.real_focal(b, 1.5)),
    }


def pair_table(lang, focals):
    """Each lens on each sensor size: equivalent, angle, coverage at 3 m and full-body distance."""
    head = "".join('<th scope="col">%s</th>' % h for h in [
        lang.t("tool.table_focal"), lang.t("tool.table_equiv"), lang.t("tool.table_h"),
        lang.t("tool.table_covers", distance=lang.metres(3, 0)),
        lang.t("tool.table_fit", height=lang.metres(lm.FULL_BODY_M))])
    groups = []
    for crop in FORMAT_CROPS:
        rows = ['<tr class="group"><th scope="colgroup" colspan="5">%s <span class="muted">%s</span></th></tr>' % (
            e(lang.format_name(crop)), lang.crop(crop))]
        for f in focals:
            rows.append("<tr><th scope=\"row\">%s</th><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                lang.mm(f), lang.mm(lm.equivalent(f, crop)), lang.deg(lm.angles(f, crop)[0]),
                lang.size(*lm.coverage(f, crop, 3)), lang.metres_feet(portrait_distances(crop, f)[0])))
        groups.append("<tbody>%s</tbody>" % "".join(rows))
    return '<div class="scroll"><table class="pair"><thead><tr>%s</tr></thead>%s</table></div>' % (
        head, "".join(groups))


def compare_page(lang, pair):
    key = compare_key(pair)
    values = compare_values(lang, pair)
    path = compare_path(pair)
    answer = lang.t(key + "_answer", **values)
    faq = [(lang.t("compare.faq_1_q", **values), answer + " " + lang.t("compare.faq_1_a", **values))]
    faq += [(lang.t("compare.faq_%d_q" % i, **values), lang.t("compare.faq_%d_a" % i, **values)) for i in (2, 3)]
    guides = [GUIDES_BY_SLUG[slug] for slug in pair["guides"]]
    others = [p for p in COMPARISONS if p is not pair]
    body = """<p class="crumbs"><a href="../../guides/">{guides}</a></p>
<h1>{h1}</h1>
<p class="lead">{answer} {numbers}</p>
<section><h2>{frames_title}</h2>
<figure class="nested-figure">{svg}<figcaption>{frames_caption}</figcaption></figure></section>
<section><h2>{choose_title}</h2><ul class="choose">{choose}</ul>
<p><a class="button secondary" href="../../lens-compare/?f={a},{b}">{open_tool}</a></p></section>
<p class="app-line">{app_line}</p>
<section><h2>{table_title}</h2><p>{table_intro}</p>{table}</section>
<section class="faq"><h2>{faq_title}</h2>{faq}</section>
<section><h2>{more_title}</h2><ul class="links">{more}</ul></section>""".format(
        guides=lang.t("nav.guides"), h1=lang.t("compare.h1", **values), answer=answer,
        numbers=lang.t("compare.lead_numbers", **values),
        frames_title=lang.t("compare.frames_title", **values),
        svg=nested_frames_svg(1.0, (pair["a"], pair["b"])),
        frames_caption=lang.t("compare.frames_caption", **values),
        choose_title=lang.t("compare.choose_title"),
        choose="".join("<li>%s</li>" % lang.t("%s_choose_%d" % (key, i), **values)
                       for i in range(1, pair["choose"] + 1)),
        a=pair["a"], b=pair["b"], open_tool=lang.t("compare.open_tool"),
        app_line=lang.with_app("app.line_compare", "web_compare_line", **values),
        table_title=lang.t("compare.table_title", **values), table_intro=lang.t("compare.table_intro"),
        table=pair_table(lang, (pair["a"], pair["b"])),
        faq_title=lang.t("home.faq_title"), faq=faq_html(lang, faq),
        more_title=lang.t("guides.more_title"),
        more=guide_links(lang, "../../", guides) + compare_links(lang, "../../", others))
    name = lang.t("compare.link", **values)
    crumbs = breadcrumbs_jsonld(lang, [("Prospekt", ""), (lang.t("nav.guides"), "guides/"), (name, path)])
    page_ld = webpage_jsonld(lang, path, lang.raw("compare.title", **values), [name])
    return Page(path, "compare.title", lang.raw("compare.description", **values), body,
                jsonld=[page_ld, faq_jsonld(faq), crumbs], title_values=values)


def guide_values(lang):
    """Numbers the guide strings can quote, by focal length: {aps_85} is the APS-C
    lens that frames like 85 mm, {eq15_50} what 50 mm frames like on APS-C, and so on."""
    values = {"crop_15": lang.crop(1.5)}
    for f in GUIDE_FOCALS:
        for name, crop in (("aps", 1.5), ("canon", 1.6), ("mft", 2.0)):
            values["%s_%d" % (name, f)] = lang.focal(lm.real_focal(f, crop))
        values["aps_%d_eq" % f] = lang.mm(lm.equivalent(lm.real_focal(f, 1.5), 1.5))
        for name, crop in (("eq15", 1.5), ("eq16", 1.6), ("eq2", 2.0)):
            values["%s_%d" % (name, f)] = lang.mm(lm.equivalent(f, crop))
        full, head = portrait_distances(1.0, f)
        values.update({
            "h_%d" % f: lang.deg(lm.angles(f, 1.0)[0]),
            "cover_%d" % f: lang.size(*lm.coverage(f, 1.0, 3)),
            "w100_%d" % f: lang.metres(lm.coverage(f, 1.0, 100)[0], 0),
            "full_%d" % f: lang.metres_feet(full), "head_%d" % f: lang.metres_feet(head),
            "full_%d_15" % f: lang.metres_feet(portrait_distances(1.5, f)[0]),
        })
    # One-off scenes: a player 30 m away, and a 4 m wall with the camera horizontal.
    values["w30_400"] = lang.metres(lm.coverage(400, 1.0, 30)[0])
    for f in (16, 24):
        values["wall_%d" % f] = lang.metres_feet(lm.distance_to_fit(4.0, f, 1.0, vertical=True, fill=1.0))
    return values


def recs_table(lang, guide):
    """Each full-frame recommendation, what it's best for, and the lens that frames about the
    same on smaller sensors. "Best for" comes second so phones show it without scrolling."""
    key = guide_key(guide)
    formats = ['<th scope="col">%s<br><span class="muted">%s</span></th>' % (
        e(lang.format_name(c)), lang.crop(c)) for c in FORMAT_CROPS]
    head = formats[0] + '<th scope="col">%s</th>' % lang.t("guide.col_use") + "".join(formats[1:])
    rows = []
    for f in guide["recs"]:
        cells = []
        for crop in FORMAT_CROPS[1:]:
            lens = lm.real_focal(f, crop)
            cell = lang.focal(lens)
            # Say what a rounded lens really frames like when it's more than a hair off.
            if abs(lm.equivalent(lens, crop) / f - 1) > 0.02:
                cell += '<br><span class="muted">%s</span>' % lang.t("guide.cell_equiv",
                                                                     equiv=lang.mm(lm.equivalent(lens, crop)))
            cells.append("<td>%s</td>" % cell)
        rows.append('<tr><th scope="row">%s</th><td class="use">%s</td>%s</tr>' % (
            lang.mm(f), lang.t("%s_use_%d" % (key, f)), "".join(cells)))
    return ('<div class="scroll"><table class="recs"><thead><tr>%s</tr></thead>'
            "<tbody>%s</tbody></table></div>") % (head, "".join(rows))


def guide_page(lang, guide, values):
    key = guide_key(guide)
    path = guide_path(guide)
    name = lang.t(key + "_name")
    faq = [(lang.t("%s_faq_%d_q" % (key, i), **values), lang.t("%s_faq_%d_a" % (key, i), **values))
           for i in range(1, 4)]
    portraits = ""
    if guide.get("portraits"):
        portraits = """<section id="portraits"><h2>{title}</h2><p>{intro}</p>{rows}
<h3>{formats_title}</h3><p>{formats_intro}</p>{formats_table}</section>""".format(
            title=lang.t("tool.portrait_title"), intro=lang.t("tool.portrait_intro"),
            rows=portrait_list(lang, 1.0, "tool.portrait_row"),
            formats_title=lang.t("tool.portrait_formats_title"),
            formats_intro=lang.t("tool.portrait_formats_intro"), formats_table=portrait_formats_table(lang))
    pairs = [p for p in COMPARISONS if guide["slug"] in p["guides"]]
    others = [g for g in GUIDES if g is not guide]
    body = """<p class="crumbs"><a href="../../guides/">{guides}</a></p>
<h1>{h1}</h1>
<p class="lead">{answer}</p>
<section><h2>{table_title}</h2><p>{table_intro}</p>{table}
<p><a class="button secondary" href="../../lens-compare/?f={focals}">{open_tool}</a></p></section>
<section><h2>{why_title}</h2>{why}</section>
{portraits}
<p class="app-line">{app_line}</p>
<section class="faq"><h2>{faq_title}</h2>{faq}</section>
<section><h2>{more_title}</h2><ul class="links">{more}</ul></section>""".format(
        guides=lang.t("nav.guides"), h1=lang.t(key + "_h1"), answer=lang.t(key + "_answer", **values),
        table_title=lang.t("guide.table_title"), table_intro=lang.t("guide.table_intro"),
        table=recs_table(lang, guide), focals=",".join(str(f) for f in sorted(guide["recs"])),
        open_tool=lang.t("guide.open_tool"), why_title=lang.t("guide.why_title"),
        why="".join("<p>%s</p>" % lang.t("%s_why_%d" % (key, i), **values) for i in range(1, 4)),
        portraits=portraits,
        app_line=lang.with_app(guide.get("app_key", "app.line_guide"), "web_guide_line"),
        faq_title=lang.t("home.faq_title"), faq=faq_html(lang, faq), more_title=lang.t("guides.more_title"),
        more=compare_links(lang, "../../", pairs) + guide_links(lang, "../../", others))
    crumbs = breadcrumbs_jsonld(lang, [("Prospekt", ""), (lang.t("nav.guides"), "guides/"), (name, path)])
    page_ld = webpage_jsonld(lang, path, lang.raw("guide.title", name=html.unescape(name)), [name])
    return Page(path, "guide.title", lang.raw(key + "_answer", **values), body,
                jsonld=[page_ld, faq_jsonld(faq), crumbs], title_values={"name": html.unescape(name)})


def guides_page(lang, values):
    """The hub: every guide and comparison with its one-line answer."""
    def item(href, name, summary):
        return '<li><a href="%s">%s</a><span class="summary">%s</span></li>' % (href, name, summary)
    uses = "".join(item("../" + guide_path(g), lang.t(guide_key(g) + "_name"),
                        lang.t(guide_key(g) + "_answer", **values)) for g in GUIDES)
    pairs = []
    for p in COMPARISONS:
        pv = compare_values(lang, p)
        pairs.append(item("../" + compare_path(p), lang.t("compare.link", **pv),
                          lang.t(compare_key(p) + "_answer", **pv)))
    body = """<h1>{h1}</h1>
<p class="lead">{lead}</p>
<section><h2>{uses_title}</h2><ul class="guide-list">{uses}</ul></section>
<section><h2>{compare_title}</h2><ul class="guide-list">{pairs}</ul></section>
<p class="app-line">{app_line}</p>
<p><a class="button secondary" href="../lens-compare/">{try_tool}</a></p>""".format(
        h1=lang.t("guides.h1"), lead=lang.t("guides.lead"), uses_title=lang.t("guides.uses_title"),
        uses=uses, compare_title=lang.t("guides.compare_title"), pairs="".join(pairs),
        app_line=lang.with_app("app.line_guides", "web_guides_line"), try_tool=lang.t("cta.try_tool"))
    crumbs = breadcrumbs_jsonld(lang, [("Prospekt", ""), (lang.t("nav.guides"), "guides/")])
    about = [lang.t(guide_key(g) + "_name") for g in GUIDES] + [
        lang.t("compare.link", a=lang.mm(p["a"]), b=lang.mm(p["b"])) for p in COMPARISONS]
    page_ld = webpage_jsonld(lang, "guides/", lang.raw("guides.title"), about)
    page_ld["@type"] = "CollectionPage"
    return Page("guides/", "guides.title", lang.raw("guides.description"), body, jsonld=[page_ld, crumbs])


def not_found_page(lang):
    """GitHub Pages serves /404.html for any missing path, so its links start at the site root."""
    body = """<h1>{title}</h1>
<p class="lead">{lead}</p>
<ul class="links"><li><a href="/">{home}</a></li><li><a href="/lens-compare/">{tool}</a></li><li><a href="/cameras/">{cameras}</a></li><li><a href="/guides/">{guides}</a></li></ul>""".format(
        title=lang.t("notfound.title"), lead=lang.t("notfound.lead"), home=lang.t("notfound.home"),
        tool=lang.t("nav.tool"), cameras=lang.t("nav.cameras"), guides=lang.t("nav.guides"))
    return Page("", "notfound.title", lang.raw("notfound.lead"), body, noindex=True, root="/")


# ---------------------------------------------------------------- outputs

def sitemap(paths):
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for path in paths:
        for lang in ALL_LANGS:
            out.append("<url><loc>%s</loc><lastmod>%s</lastmod>" % (e(url_for(lang, path)), SITE_UPDATED))
            for other in ALL_LANGS:
                out.append('<xhtml:link rel="alternate" hreflang="%s" href="%s"/>' % (other.code, e(url_for(other, path))))
            out.append("</url>")
    for static in ["support.html", "privacy.html", "terms.html"]:
        out.append("<url><loc>%s/%s</loc></url>" % (BASE_URL, static))
    out.append("</urlset>")
    return "\n".join(out) + "\n"


ROBOTS = """# Search engines and AI assistants are welcome to read and cite every page.
User-agent: *
Allow: /

User-agent: GPTBot
Allow: /

User-agent: OAI-SearchBot
Allow: /

User-agent: ChatGPT-User
Allow: /

User-agent: ClaudeBot
Allow: /

User-agent: Claude-SearchBot
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Google-Extended
Allow: /

User-agent: Bingbot
Allow: /

Sitemap: {base}/sitemap.xml
"""


def llms_txt(bodies):
    lines = [
        "# Prospekt",
        "",
        "> Prospekt is an iPhone lens simulator: a live viewfinder that shows what a 14 to 300 mm lens "
        "frames on your camera body. 59 bodies built in, custom bodies, 1.4x and 2x extenders. "
        "$3.99 once, no subscription, no account, works offline. iPhone only, iOS 17 or later. "
        "It shows framing, not depth of field or bokeh. Made by nakolini (Vitalii Kikot and Dmytro Hryb).",
        "",
        "## Pages",
        "",
        "- [Prospekt for iPhone](%s/): what it does, price, privacy, limits, comparison, FAQ" % BASE_URL,
        "- [Lens comparison tool](%s/lens-compare/): free web tool, frames of any focal lengths and zooms on one or two "
        "bodies over a photo or a standing person drawn to scale, how much of the scene each lens covers at a distance, and how far to stand to fit a "
        "subject (metres or feet). The distance calculator is part of the web tool, not the app" % BASE_URL,
        "- [Cameras](%s/cameras/): focal length, full-frame equivalent and angle of view tables for %d camera bodies, "
        "what 24 to 135 mm cover at 1 to 10 m, and portrait distances (full body, head and shoulders)" % (BASE_URL, len(bodies)),
        "- [Changelog](%s/changelog/): every release" % BASE_URL,
        "- [App Store](https://apps.apple.com/app/id%s)" % APP_ID,
        "",
    ] + guides_llms(ALL_LANGS[0]) + [
        "## Facts",
        "",
        "- App Store name: %s (localized: %s)" % (STORE["en"]["name"], "; ".join(sorted(
            {v["name"] for k, v in STORE.items() if v["name"] != STORE["en"]["name"]}))),
        "- App Store: https://apps.apple.com/app/id%s, sold by Vitalii Kikot, co-founder of nakolini" % APP_ID,
        "- Version %s, released %s. Site updated %s" % (STORE["en"]["version"], STORE["en"]["released"], SITE_UPDATED),
        "- Price: one-time purchase, no subscription, no in-app purchases. %s" % ", ".join(
            "%s %s" % (v["storefront"].upper(), v["price"].replace("\u00a0", " ")) for k, v in STORE.items() if k != "ar"),
        "- Platform: iPhone, iOS 17 or later. No Android or iPad version. Works offline; no account, no analytics, no ads",
        "- What it does: a live viewfinder that crops the iPhone camera to the field of view of a 14 to 300 mm lens on "
        "a chosen camera body, with 1.4x and 2x extenders and custom bodies",
        "- What it doesn't do: depth of field, bokeh, distortion or lens rendering. Below about 13 mm equivalent the "
        "iPhone's ultra-wide is the limit, and long focal lengths use digital zoom, so they look soft. For cinema cameras and cine lenses, a director's viewfinder such as "
        "Artemis or Cadrage fits better",
        "",
        "## Languages",
        "",
        "Every page is available in: %s." % ", ".join("%s (%s/%s)" % (l.name, BASE_URL, l.prefix) for l in ALL_LANGS),
        "",
    ]
    return "\n".join(lines)


def guides_llms(lang):
    """The Guides section of llms.txt: each question page with its one-line answer, in English."""
    def plain(text):
        return text.replace("\u00a0", " ")
    values = guide_values(lang)
    lines = ["## Guides", "",
             "- [Focal length guides](%s/guides/): %s" % (BASE_URL, plain(lang.raw("guides.description")))]
    for pair in COMPARISONS:
        pv = compare_values(lang, pair)
        lines.append("- [%s](%s/%s): %s" % (plain(lang.raw("compare.link", **pv)), BASE_URL, compare_path(pair),
                                            plain(lang.raw(compare_key(pair) + "_answer", **pv))))
    for guide in GUIDES:
        key = guide_key(guide)
        lines.append("- [%s](%s/%s): %s" % (plain(lang.raw(key + "_name")), BASE_URL, guide_path(guide),
                                            plain(lang.raw(key + "_answer", **values))))
    return lines + [""]


def write(path, content):
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


def clean():
    for d in GENERATED_DIRS:
        shutil.rmtree(os.path.join(ROOT, d), ignore_errors=True)
    for f in GENERATED_FILES:
        if os.path.exists(os.path.join(ROOT, f)):
            os.remove(os.path.join(ROOT, f))


ALL_LANGS = []


def build():
    ALL_LANGS[:] = load_languages()
    bodies = load_bodies()
    clean()
    paths = []
    for lang in ALL_LANGS:
        values = guide_values(lang)
        pages = [home_page(lang), tool_page(lang, bodies), cameras_page(lang, bodies), changelog_page(lang)]
        pages += [body_page(lang, body, bodies) for body in bodies]
        pages += [guides_page(lang, values)] + [compare_page(lang, pair) for pair in COMPARISONS]
        pages += [guide_page(lang, guide, values) for guide in GUIDES]
        for page in pages:
            write(lang.prefix + page.path + "index.html", render(lang, page))
        if lang.code == "en":
            paths = [page.path for page in pages]
    # English only: GitHub Pages serves one 404 page for every path.
    write("404.html", render(ALL_LANGS[0], not_found_page(ALL_LANGS[0])))
    write("sitemap.xml", sitemap(paths))
    write("robots.txt", ROBOTS.format(base=BASE_URL))
    write("llms.txt", llms_txt(bodies))
    write(".nojekyll", "")
    write("CNAME", BASE_URL.split("://", 1)[1] + "\n")
    # IndexNow proves we own the host with a public key file at its root.
    write(INDEXNOW_KEY + ".txt", INDEXNOW_KEY + "\n")
    return len(ALL_LANGS), len(paths)


if __name__ == "__main__":
    langs, pages = build()
    print("built %d pages in %d languages" % (pages * langs, langs))

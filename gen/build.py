"""Builds the static site from data/, i18n/ and the templates below.

Usage: python3 gen/build.py   (or `make build`)

English is served at the root, every other language under /<lang>/.
A language is built when i18n/<code>.json exists. Every link is relative,
so the output works under any host or sub-path; only canonical URLs,
hreflang, the sitemap and robots.txt use BASE_URL.
"""

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
THREADS_URL = "https://www.threads.net/@dmytro.builds"
ANONIMO_URL = "https://apps.apple.com/app/id6762560095"
EXPENNY_URL = "https://apps.apple.com/app/id6758223013"

# Sample photos for the tool, each credited in the footer of pages that show it.
SAMPLES = [
    {"src": "assets/sample-14mm.jpg", "small": "assets/sample-14mm-1200.jpg", "width": 1920, "height": 1280,
     "focal": 14.0, "label_key": "tool.photo_sample", "credit_key": "footer.photo_credit"},
    # Canon EOS R5 at 10 mm, trimmed from 8192 to 8013 px wide on Commons: 10 x 8192 / 8013.
    {"src": "assets/sample-10mm.jpg", "small": None, "width": 1920, "height": 1280,
     "focal": 10.2, "label_key": "tool.photo_sample_10", "credit_key": "footer.photo_credit_10"},
    # Canon EOS 5D Mark IV at 20 mm, full 6720 x 4480 frame.
    {"src": "assets/sample-20mm.jpg", "small": None, "width": 1920, "height": 1280,
     "focal": 20.0, "label_key": "tool.photo_sample_20", "credit_key": "footer.photo_credit_20"},
]
SAMPLE = SAMPLES[0]

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

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
GENERATED_DIRS = ["lens-compare", "cameras", "changelog"] + [s for _, s, _ in LANGUAGES if s]
GENERATED_FILES = ["index.html", "sitemap.xml", "robots.txt", "llms.txt", ".nojekyll", "CNAME",
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


def e(text):
    return html.escape(str(text), quote=True)


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

    @property
    def prefix(self):
        return self.segment + "/" if self.segment else ""

    def t(self, key, **values):
        """A translated string with {placeholders} filled, HTML-escaped."""
        return e(self.raw(key, **values))

    def raw(self, key, **values):
        template = self.strings.get(key, self.fallback.get(key))
        if template is None:
            raise KeyError(key)
        values.setdefault("price", PRICE)
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
                 extra_head="", scripts=""):
        self.path = path  # "", "lens-compare/", "cameras/canon-r7/"
        self.title_key = title_key
        self.title_values = title_values or {}
        self.description = description
        self.body = body
        self.jsonld = jsonld or []
        self.extra_head = extra_head
        self.scripts = scripts


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
<a class="brand" href="{home}">Prospekt</a>
<nav aria-label="Prospekt"><a href="{home}lens-compare/">{tool}</a><a href="{home}cameras/">{cameras}</a><a class="nav-app" href="{app}">{get}</a></nav>
<details class="lang"><summary>{langlabel}: {langname}</summary><ul>{switch}</ul></details>
</div></header>""".format(
        skip=lang.t("nav.skip"), home=home, tool=lang.t("nav.tool"), cameras=lang.t("nav.cameras"),
        app=e(app_store_url("web_nav")), get=lang.t("nav.get_app"), langlabel=lang.t("nav.language"),
        langname=e(lang.name), switch=switch)


def footer(lang, root, credit_keys):
    home = root + lang.prefix
    credit = "".join('<p class="credit">%s</p>' % lang.t(k) for k in credit_keys)
    return """<footer class="site-footer"><div class="wrap">
<p>{made} <a href="{threads}" rel="me">Threads</a></p>
<p>{also} <a href="{anonimo}">{anonimo_t}</a> · <a href="{expenny}">{expenny_t}</a></p>
<p><a href="{home}changelog/">{changelog}</a> · <a href="{root}support.html">{support}</a> · <a href="{root}privacy.html">{privacy}</a> · <a href="{root}terms.html">{terms}</a></p>
{credit}
</div></footer>""".format(
        made=lang.t("footer.made_by"), threads=THREADS_URL, also=lang.t("footer.also"),
        anonimo=e(ANONIMO_URL + "?ct=web_prospekt&mt=8"), anonimo_t=lang.t("footer.anonimo"),
        expenny=e(EXPENNY_URL + "?ct=web_prospekt&mt=8"), expenny_t=lang.t("footer.expenny"),
        home=home, root=root, changelog=lang.t("nav.changelog"), support=lang.t("footer.support"),
        privacy=lang.t("footer.privacy"), terms=lang.t("footer.terms"), credit=credit)


def render(lang, page):
    root = rel_root(lang, page.path)
    title = lang.t(page.title_key, **page.title_values)
    canonical = url_for(lang, page.path)
    alternates = "".join(
        '<link rel="alternate" hreflang="%s" href="%s">\n' % (other.code, e(url_for(other, page.path)))
        for other in ALL_LANGS)
    alternates += '<link rel="alternate" hreflang="x-default" href="%s">\n' % e(url_for(ALL_LANGS[0], page.path))
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
<link rel="canonical" href="{canonical}">
{alternates}<meta property="og:type" content="website">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{og_image}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#1a1a1a">
<meta name="apple-itunes-app" content="app-id={app_id}">
<link rel="stylesheet" href="{root}assets/site.css">
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
        code=lang.code, dir=lang.dir, title=title, description=e(page.description),
        canonical=e(canonical), alternates=alternates, og_image=e(BASE_URL + "/" + SAMPLE["small"]),
        app_id=APP_ID, root=root, extra_head=page.extra_head, jsonld=jsonld,
        header=header(lang, root, page.path), body=page.body.replace("{root}", root),
        footer=footer(lang, root, credits), scripts=page.scripts.replace("{root}", root))


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


def app_jsonld(lang):
    return {
        "@context": "https://schema.org",
        "@type": "MobileApplication",
        "name": "Prospekt",
        "alternateName": "Lens Simulator: Prospekt",
        "description": lang.raw("home.description"),
        "inLanguage": lang.code,
        "operatingSystem": "iOS 17.0 or later",
        "applicationCategory": "PhotographyApplication",
        "url": url_for(lang, ""),
        "downloadUrl": "https://apps.apple.com/app/id%s" % APP_ID,
        "installUrl": "https://apps.apple.com/app/id%s" % APP_ID,
        "offers": {"@type": "Offer", "price": "3.99", "priceCurrency": "USD"},
        "publisher": organization_jsonld(),
        "author": organization_jsonld(),
        "sameAs": ["https://apps.apple.com/app/id%s" % APP_ID],
    }


# ---------------------------------------------------------------- pages

def home_page(lang):
    faq = [(lang.t("home.faq_%d_q" % i), lang.t("home.faq_%d_a" % i)) for i in range(1, 10)]
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
        faq_title=lang.t("home.faq_title"), faq=faq_html(lang, faq), cta_box=cta_box(lang, "web_home"))
    return Page("", "home.title", lang.raw("home.description"), body,
                jsonld=[app_jsonld(lang), faq_jsonld(faq)])


def equivalence_table(lang):
    head = "".join('<th scope="col">%s<br><span class="muted">%s</span></th>' % (
        e(lang.format_name(c)), lang.crop(c)) for c in GENERIC_CROPS[1:])
    rows = "".join("<tr><th scope=\"row\">%s</th>%s</tr>" % (
        lang.mm(eq), "".join("<td>%s</td>" % lang.mm(lm.focal_for_equivalent(eq, c)) for c in GENERIC_CROPS[1:]))
        for eq in lm.CLASSIC_EQUIVALENTS)
    return '<div class="scroll"><table><thead><tr><th scope="col">%s</th>%s</tr></thead><tbody>%s</tbody></table></div>' % (
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


def body_options(lang, bodies):
    generic = "".join('<option value="generic-%s" data-crop="%s">%s (%s)</option>' % (
        ("%g" % c).replace(".", "_"), c, e(lang.format_name(c)), lang.crop(c)) for c in GENERIC_CROPS)
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


TOOL_JS_KEYS = ["tool.too_wide", "tool.preview_title", "tool.copied", "tool.share",
                "tool.table_focal", "tool.table_equiv", "tool.table_h", "tool.table_v", "tool.table_d",
                "tool.table_covers", "tool.table_fit_v", "tool.table_fit_h"]

ZOOM_PRESETS = [(10, 18), (16, 35), (18, 55), (24, 70), (24, 105), (28, 75), (70, 200), (100, 400), (150, 600)]


def tool_page(lang, bodies):
    faq_values = {"d%d" % f: lang.metres_feet(portrait_distances(1.0, f)[0]) for f in lm.PORTRAIT_FOCAL_LENGTHS}
    faq = [(lang.t("tool.faq_%d_q" % i), lang.t("tool.faq_%d_a" % i, **faq_values)) for i in range(1, 5)]
    default_focals = [24, 35, 50, 85]
    chips = "".join('<button type="button" class="chip" data-focal="%d" aria-pressed="%s">%d</button>' % (
        f, "true" if f in default_focals else "false", f) for f in lm.TABLE_FOCAL_LENGTHS)
    zoom_chips = "".join('<button type="button" class="chip" data-zoom="%d-%d" aria-pressed="false">%d-%d</button>' % (
        a, b, a, b) for a, b in ZOOM_PRESETS)
    strings = {k: lang.raw(k, focal="{focal}", distance="{distance}", height="{height}") for k in TOOL_JS_KEYS}
    data = json.dumps({"strings": strings, "samples": SAMPLES, "lang": lang.code,
                       "comma": lang.code in DECIMAL_COMMA, "rtl": lang.dir == "rtl",
                       "fill": lm.PORTRAIT_FILL, "foot": lm.FOOT_M},
                      ensure_ascii=False).replace("</", "<\\/")
    samples = "".join('<label class="inline"><input type="radio" name="photo" value="sample-%d"%s> %s</label>' % (
        i, " checked" if i == 0 else "", lang.t(sample["label_key"])) for i, sample in enumerate(SAMPLES))
    options = body_options(lang, bodies)
    body = """<h1>{h1}</h1>
<p class="lead">{lead}</p>
<noscript><p class="note">{noscript}</p></noscript>
<form id="tool" class="tool" hidden>
<div class="controls">
<label>{body_label}<select id="body">{options}</select></label>
<label>{body2_label}<select id="body2"><option value="">{body2_none}</option>{options}</select></label>
<fieldset class="wide"><legend>{focals_label}</legend><div class="chips" id="chips">{chips}</div>
<label class="inline">{custom_label} <input id="custom" type="number" min="4" max="1200" step="1" inputmode="numeric"> <button type="button" id="add">{add}</button></label>
<p class="sublabel" id="zooms-label">{zooms_label}</p>
<div class="chips" id="zooms" role="group" aria-labelledby="zooms-label">{zoom_chips}</div>
<div class="inline-row"><span id="zoom-custom-label">{zoom_custom_label}</span> <span class="range"><input id="zoom-from" type="number" min="4" max="1200" step="1" inputmode="numeric" aria-label="{zoom_from}"> <span aria-hidden="true">-</span> <input id="zoom-to" type="number" min="4" max="1200" step="1" inputmode="numeric" aria-label="{zoom_to}"></span> <button type="button" id="add-zoom" aria-describedby="zoom-custom-label">{add}</button></div>
</fieldset>
<fieldset><legend>{distance_legend}</legend>
<div class="field"><label for="distance">{distance_label}</label> <span class="with-unit"><input id="distance" type="number" min="0.1" max="100000" step="0.1" value="3" inputmode="decimal"> <span class="unit">m</span></span></div>
<div class="segmented" role="radiogroup" aria-label="{unit_label}"><label><input type="radio" name="unit" value="m" checked> {unit_m}</label><label><input type="radio" name="unit" value="ft"> {unit_ft}</label></div>
<div class="field"><label for="subject">{subject_label}</label> <span class="with-unit"><input id="subject" type="number" min="0.01" max="100000" step="0.1" value="1.8" inputmode="decimal"> <span class="unit">m</span></span></div>
<div class="segmented" role="radiogroup" aria-label="{subject_label}"><label><input type="radio" name="orient" value="v" checked> {vertical}</label><label><input type="radio" name="orient" value="h"> {horizontal}</label></div>
<p class="muted">{subject_hint}</p>
</fieldset>
<fieldset><legend>{photo_label}</legend>
{samples}
<label class="inline"><input type="radio" name="photo" value="own"> {photo_own}</label>
<div id="own" hidden><input id="file" type="file" accept="image/*">
<label>{photo_focal_label} <input id="photo-focal" type="number" min="4" max="1200" step="0.1" value="26"></label>
<p class="muted">{photo_focal_hint}</p><p class="muted">{photo_private}</p></div></fieldset>
</div>
<div class="stage">
<div class="photo-frame" id="stage"><img id="photo" src="{{root}}{src}" data-root="{{root}}" width="{w}" height="{h}" alt="">{frames}</div>
<p class="legend" id="legend" hidden></p>
<p class="muted" id="notes"></p>
<div id="results">{table}</div>
<p class="muted">{preview_hint} {distance_note} {soft}</p>
<figure class="preview" id="preview" hidden><canvas id="preview-canvas"></canvas><figcaption id="preview-caption"></figcaption></figure>
<p><button type="button" id="share">{share}</button> <span id="share-status" role="status"></span></p>
</div>
</form>
<figure class="photo" id="static-figure"><div class="photo-frame"><img src="{{root}}{small}" width="1200" height="800" alt="" loading="lazy">{frames}</div>
<figcaption>{static_caption}</figcaption></figure>
<section><h2>{equiv_title}</h2><p>{equiv_intro}</p>{equiv_table}</section>
<section id="distances"><h2>{distance_title}</h2><p>{distance_intro}</p>{distance_table}</section>
<section id="portraits"><h2>{portrait_title}</h2><p>{portrait_intro}</p>{portraits}</section>
<section><h2>{math_title}</h2><ul>{math}</ul></section>
<section class="faq"><h2>{faq_title}</h2>{faq}</section>
{cta_box}
<script type="application/json" id="tool-data">{data}</script>""".format(
        h1=lang.t("tool.h1"), lead=lang.t("tool.lead"), noscript=lang.t("tool.noscript"),
        body_label=lang.t("tool.body_label"), options=options, body2_label=lang.t("tool.body2_label"),
        body2_none=lang.t("tool.body2_none"),
        focals_label=lang.t("tool.focals_label"), chips=chips, custom_label=lang.t("tool.custom_label"),
        add=lang.t("tool.add"), zooms_label=lang.t("tool.zooms_label"), zoom_chips=zoom_chips,
        zoom_custom_label=lang.t("tool.zoom_custom_label"), zoom_from=lang.t("tool.zoom_from"),
        zoom_to=lang.t("tool.zoom_to"), distance_legend=lang.t("tool.distance_legend"),
        distance_label=lang.t("tool.distance_label"), unit_label=lang.t("tool.unit_label"),
        unit_m=lang.t("tool.unit_m"), unit_ft=lang.t("tool.unit_ft"), subject_label=lang.t("tool.subject_label"),
        vertical=lang.t("tool.subject_vertical"), horizontal=lang.t("tool.subject_horizontal"),
        subject_hint=lang.t("tool.subject_hint"), photo_label=lang.t("tool.photo_label"),
        samples=samples, photo_own=lang.t("tool.photo_own"),
        photo_focal_label=lang.t("tool.photo_focal_label"), photo_focal_hint=lang.t("tool.photo_focal_hint"),
        photo_private=lang.t("tool.photo_private"), src=SAMPLE["src"], small=SAMPLE["small"],
        w=SAMPLE["width"], h=SAMPLE["height"], frames=photo_frames_svg(default_focals, 1.0),
        table=angle_table(lang, default_focals, 1.0), preview_hint=lang.t("tool.preview_hint"),
        distance_note=lang.t("tool.distance_note"), soft=lang.t("tool.soft_note"), share=lang.t("tool.share"),
        static_caption=lang.t("tool.static_caption"), equiv_title=lang.t("tool.equiv_title"),
        equiv_intro=lang.t("tool.equiv_intro"), equiv_table=equivalence_table(lang),
        distance_title=lang.t("tool.distance_title"), distance_intro=lang.t("tool.distance_intro"),
        distance_table=coverage_table(lang, 1.0), portrait_title=lang.t("tool.portrait_title"),
        portrait_intro=lang.t("tool.portrait_intro"), portraits=portrait_list(lang, 1.0, "tool.portrait_row"),
        math_title=lang.t("tool.math_title"),
        math="".join("<li>%s</li>" % lang.t("tool.math_%d" % i) for i in range(1, 6)),
        faq_title=lang.t("home.faq_title"), faq=faq_html(lang, faq),
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
    }
    crumbs = breadcrumbs_jsonld(lang, [("Prospekt", ""), (lang.t("nav.tool"), "lens-compare/")])
    return Page("lens-compare/", "tool.title", lang.raw("tool.description"), body,
                jsonld=[app, faq_jsonld(faq), crumbs],
                scripts='<script src="{root}assets/lens-compare.js" defer></script>\n')


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
    }
    if math.isclose(crop, 1.0):
        intro = lang.t("body.intro_ff", **values)
    else:
        intro = lang.t("body.intro", **values)
    mount = "<p>%s</p>" % lang.t("body.mount", mount=body["mount"]) if body.get("mount") else ""
    note = "<p class=\"note\">%s</p>" % lang.t(body["note_key"]) if body.get("note_key") else ""
    classic = "".join("<li>%s</li>" % lang.t("body.classic_row", equiv=lang.mm(eq), body=name,
                                               focal=lang.mm(lm.focal_for_equivalent(eq, crop)))
                      for eq in lm.CLASSIC_EQUIVALENTS)
    same = [b for b in bodies if math.isclose(b["crop"], crop) and b["slug"] != body["slug"]]
    same_html = ", ".join('<a href="../%s/">%s</a>' % (b["slug"], e(b["display"])) for b in same)
    # The app question stays last.
    faq = [(lang.t("body.faq_%d_q" % i, **values), lang.t("body.faq_%d_a" % i, **values)) for i in [1, 2, 4, 5, 3]]
    page_body = """<p class="crumbs"><a href="../">{cameras}</a></p>
<h1>{h1}</h1>
<p class="lead">{intro}</p>
{mount}{note}
<p><a class="button secondary" href="../../lens-compare/?body={slug}">{open_tool}</a></p>
<section><h2>{frames_title}</h2>
<figure class="nested-figure">{svg}<figcaption>{frames_caption}</figcaption></figure></section>
<section><h2>{table_title}</h2>{table}</section>
<section><h2>{classic_title}</h2><p>{classic_intro}</p><ul>{classic}</ul></section>
<section id="distances"><h2>{distance_title}</h2><p>{distance_intro}</p>{distance_table}</section>
<section id="portraits"><h2>{portrait_title}</h2><p>{portrait_intro}</p>{portraits}</section>
<section class="faq"><h2>{faq_title}</h2>{faq}</section>
{cta_box}
<section><h2>{same_title}</h2><p>{same}</p></section>""".format(
        cameras=lang.t("nav.cameras"), h1=lang.t("body.h1", **values), intro=intro, mount=mount, note=note,
        slug=body["slug"], open_tool=lang.t("body.open_tool", **values),
        frames_title=lang.t("body.frames_title", **values),
        svg=nested_frames_svg(crop), frames_caption=lang.t("body.frames_caption", **values),
        table_title=lang.t("body.table_title", **values), table=angle_table(lang, lm.TABLE_FOCAL_LENGTHS, crop),
        classic_title=lang.t("body.classic_title", **values), classic_intro=lang.t("body.classic_intro", **values),
        classic=classic, distance_title=lang.t("body.distance_title", **values),
        distance_intro=lang.t("body.distance_intro", **values), distance_table=coverage_table(lang, crop),
        portrait_title=lang.t("body.portrait_title", **values),
        portrait_intro=lang.t("body.portrait_intro", **values),
        portraits=portrait_list(lang, crop, "body.portrait_row", body=name),
        faq_title=lang.t("home.faq_title"), faq=faq_html(lang, faq),
        cta_box=cta_box(lang, "web_body"), same_title=lang.t("body.same_format"), same=same_html)
    path = "cameras/%s/" % body["slug"]
    crumbs = breadcrumbs_jsonld(lang, [("Prospekt", ""), (lang.t("nav.cameras"), "cameras/"), (name, path)])
    return Page(path, "body.title", lang.raw("body.description", **values), page_body,
                jsonld=[faq_jsonld(faq), crumbs], title_values=values)


def changelog_page(lang):
    entries = "".join("<section><h2>%s <span class=\"muted\">%s</span></h2><ul>%s</ul></section>" % (
        e(version), lang.t(date), "".join("<li>%s</li>" % lang.t(k) for k in keys))
        for version, date, keys in CHANGELOG)
    body = "<h1>%s</h1>\n<p class=\"lead\">%s</p>\n%s\n%s" % (
        lang.t("changelog.h1"), lang.t("changelog.lead"), entries, cta_box(lang, "web_changelog"))
    return Page("changelog/", "changelog.title", lang.raw("changelog.description"), body)


# ---------------------------------------------------------------- outputs

def sitemap(paths):
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for path in paths:
        for lang in ALL_LANGS:
            out.append("<url><loc>%s</loc>" % e(url_for(lang, path)))
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
        "bodies over a photo, how much of the scene each lens covers at a distance, and how far to stand to fit a "
        "subject (metres or feet). The distance calculator is part of the web tool, not the app" % BASE_URL,
        "- [Cameras](%s/cameras/): focal length, full-frame equivalent and angle of view tables for %d camera bodies, "
        "what 24 to 135 mm cover at 1 to 10 m, and portrait distances (full body, head and shoulders)" % (BASE_URL, len(bodies)),
        "- [Changelog](%s/changelog/): every release" % BASE_URL,
        "- [App Store](https://apps.apple.com/app/id%s)" % APP_ID,
        "",
        "## Languages",
        "",
        "Every page is available in: %s." % ", ".join("%s (%s/%s)" % (l.name, BASE_URL, l.prefix) for l in ALL_LANGS),
        "",
    ]
    return "\n".join(lines)


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
        pages = [home_page(lang), tool_page(lang, bodies), cameras_page(lang, bodies), changelog_page(lang)]
        pages += [body_page(lang, body, bodies) for body in bodies]
        for page in pages:
            write(lang.prefix + page.path + "index.html", render(lang, page))
        if lang.code == "en":
            paths = [page.path for page in pages]
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

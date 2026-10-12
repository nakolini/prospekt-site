# prospekt-site

The website for [Prospekt](https://apps.apple.com/app/id6760914468), the iPhone lens simulator, live at **https://prospekt.nakolini.com** and served by GitHub Pages from `main`.

It has five kinds of pages, in 15 languages (the app's own, without Russian), all plain HTML that reads fine without JavaScript:

- `/`: what the app does, price, privacy, limits, an honest comparison, FAQ.
- `/lens-compare/`: a free lens comparison tool. Pick a body (and optionally a second one), focal lengths or zooms, and see the frames over a photo (a sample, or your own; it never leaves the browser) or over a standing person drawn to scale, with what each lens covers at a subject distance and how far to stand to fit a subject. Links are shareable: `/lens-compare/?body=fujifilm-x-t5&f=23,33,56&d=3&u=m`.
- `/cameras/` and `/cameras/<body>/`: focal length, full-frame equivalent and angle-of-view tables for every body in the app, plus what 24-135 mm cover at 1-10 m and portrait distances.
- `/guides/`, `/compare/<a>mm-vs-<b>mm/` and `/focal-length/<use>/`: question-shaped pages ("35 mm or 50 mm?", "best focal length for portraits") that answer first, then give the numbers for full frame, APS-C and Micro Four Thirds, the trade-offs and a link to the tool with those focal lengths. The pairs and uses are `COMPARISONS` and `GUIDES` in `gen/build.py`; their copy is the `compare.*`, `guide.*` and `guides.*` keys.
- `/changelog/`: every release.

`404.html` is the page GitHub Pages serves for any missing path. It's English only, kept out of search (`noindex`), and its links start at the site root (`/cameras/`) because it can be served at any depth.

English is at the root, other languages under `/<lang>/` (`/de/`, `/pt-br/`, `/zh-hans/`...), linked with hreflang.

## Commands

```
make build    # regenerate every page from data/ and i18n/
make test     # unit tests, translation parity, built-site checks (needs node for the JS parity test)
make check    # build + test + fail if the committed output is stale (CI runs this)
make bodies   # re-export the camera list from ../prospekt (PROSPEKT=path to override)
make serve    # http://localhost:8000
```

Python 3.9+ standard library only. No dependencies.

## Where things live

- `gen/build.py`: the generator and every page template. `BASE_URL` (canonical host) and `PROVIDER_TOKEN` (App Store campaign attribution) are at the top.
- Pages link `site.css` and `lens-compare.js` with `?v=` and a hash of their content (`asset_url`), so a deploy never pairs new HTML with a cached old file. Rebuild after editing either.
- `gen/lensmath.py`: field-of-view math. `assets/lens-compare.js` has the same formulas for the tool; `gen/tests/test_js_parity.py` keeps them identical.
- `data/bodies.json`: generated from the app's `CameraBody.curated`; never edit by hand. `data/mounts.json`: lens mount per body, edited by hand. The tests fail if a body has no mount entry.
- `i18n/<lang>.json`: all page copy. `en.json` is the source; every other file must have the same keys and `{placeholders}` (tested).
- `support.html`, `privacy.html`, `terms.html`: hand-written, English only, linked from the App Store listing. Don't move them.
- `favicon.ico` and `assets/icon-*.png`, `assets/apple-touch-icon.png`: the app icon for browser tabs, the header logo, home-screen bookmarks and the app's JSON-LD `image`. Made from the app's `AppIcon.png` (1024 px, square) with ImageMagick: the PNGs and the `.ico` get iOS-style rounded corners (radius 22.4 % of the side) over transparency, the touch icon stays square because iOS rounds it itself.
- Everything else at the root except `favicon.ico` (`index.html`, `CNAME`, the IndexNow key file, `lens-compare/`, `cameras/`, `changelog/`, `<lang>/`, `sitemap.xml`, `robots.txt`, `llms.txt`) is generated. Edit the generator, not the output.

## Changing things

- **New camera in the app:** `make bodies`, add its mount to `data/mounts.json`, `make build`.
- **New app version:** add the notes to `CHANGELOG` in `gen/build.py` and the strings to every `i18n/*.json`.
- **Copy change:** edit `i18n/en.json`, then update the same key in every other language. A key missing from a language falls back to English in the build, but the i18n tests fail until it's translated.
- **New comparison or guide:** add it to `COMPARISONS` or `GUIDES` in `gen/build.py` and its strings to `i18n/*.json` (`compare.<a>_<b>_answer` and `_choose_<n>`, or `guide.<slug>_name`, `_h1`, `_answer`, `_why_1-3`, `_use_<focal>`, `_faq_1-3_q/_a`).
- **Domain:** the site is served at `https://prospekt.nakolini.com` (Cloudflare CNAME `prospekt` → `nakolini.github.io`, DNS only). `BASE_URL` in `gen/build.py` drives canonical URLs, hreflang, the sitemap and the generated `CNAME` file; GitHub redirects the old `nakolini.github.io/prospekt-site/` URLs there.
- **Search engines:** after a deploy that adds or renames pages, run `python3 scripts/indexnow.py` to notify Bing, Yandex, Seznam and Naver (the `<key>.txt` file at the root proves ownership). Google reads `sitemap.xml` from `robots.txt`; submit it once in Search Console.

The person scene in the tool (the "Person" tile) is drawn by `assets/lens-compare.js` (`drawScene`), so it needs no credit. Sample photos (`SAMPLES` in `gen/build.py`, each credited in the footer of pages that show it):

- [Montmorency station entrance](https://commons.wikimedia.org/wiki/File:Montmorency_station_entrance,_October_13,_2021.jpg) by D. Benjamin Miller, CC0 (Canon EOS R5, 14 mm).
- [David Geffen Hall with fountain in the foreground](https://commons.wikimedia.org/wiki/File:David_Geffen_Hall_with_fountain_in_the_foreground,_March_14,_2024.jpg) by D. Benjamin Miller, CC0 (Canon EOS R5, 10 mm; trimmed slightly on Commons, so the tool uses 10.2 mm).
- [Liqeni Artificial i Tiranës 05](https://commons.wikimedia.org/wiki/File:Liqeni_Artificial_i_Tiran%C3%ABs_05_-_%C2%A9_Shk%C3%ABlzen_Rexha.jpg) by Shkelzen A. Rexha, CC0 (Canon EOS 5D Mark IV, 20 mm).

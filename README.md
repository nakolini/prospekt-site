# prospekt-site

The website for [Prospekt](https://apps.apple.com/app/id6760914468), the iPhone lens simulator, live at **https://prospekt.nakolini.com** and served by GitHub Pages from `main`.

It has four kinds of pages, in 15 languages (the app's own, without Russian), all plain HTML that reads fine without JavaScript:

- `/`: what the app does, price, privacy, limits, an honest comparison, FAQ.
- `/lens-compare/`: a free lens comparison tool. Pick a body (and optionally a second one), focal lengths or zooms, and see the frames over a photo (a sample, or your own; it never leaves the browser) or over a standing person drawn to scale, with what each lens covers at a subject distance and how far to stand to fit a subject. Links are shareable: `/lens-compare/?body=fujifilm-x-t5&f=23,33,56&d=3&u=m`.
- `/cameras/` and `/cameras/<body>/`: focal length, full-frame equivalent and angle-of-view tables for every body in the app, plus what 24-135 mm cover at 1-10 m and portrait distances.
- `/changelog/`: every release.

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
- `gen/lensmath.py`: field-of-view math. `assets/lens-compare.js` has the same formulas for the tool; `gen/tests/test_js_parity.py` keeps them identical.
- `data/bodies.json`: generated from the app's `CameraBody.curated`; never edit by hand. `data/mounts.json`: lens mount per body, edited by hand. The tests fail if a body has no mount entry.
- `i18n/<lang>.json`: all page copy. `en.json` is the source; every other file must have the same keys and `{placeholders}` (tested).
- `support.html`, `privacy.html`, `terms.html`: hand-written, English only, linked from the App Store listing. Don't move them.
- Everything else at the root (`index.html`, `CNAME`, the IndexNow key file, `lens-compare/`, `cameras/`, `changelog/`, `<lang>/`, `sitemap.xml`, `robots.txt`, `llms.txt`) is generated. Edit the generator, not the output.

## Changing things

- **New camera in the app:** `make bodies`, add its mount to `data/mounts.json`, `make build`.
- **New app version:** add the notes to `CHANGELOG` in `gen/build.py` and the strings to every `i18n/*.json`.
- **Copy change:** edit `i18n/en.json`, then update the same key in every other language.
- **Domain:** the site is served at `https://prospekt.nakolini.com` (Cloudflare CNAME `prospekt` → `nakolini.github.io`, DNS only). `BASE_URL` in `gen/build.py` drives canonical URLs, hreflang, the sitemap and the generated `CNAME` file; GitHub redirects the old `nakolini.github.io/prospekt-site/` URLs there.
- **Search engines:** after a deploy that adds or renames pages, run `python3 scripts/indexnow.py` to notify Bing, Yandex, Seznam and Naver (the `<key>.txt` file at the root proves ownership). Google reads `sitemap.xml` from `robots.txt`; submit it once in Search Console.

The person scene in the tool (the "Person" tile) is drawn by `assets/lens-compare.js` (`drawScene`), so it needs no credit. Sample photos (`SAMPLES` in `gen/build.py`, each credited in the footer of pages that show it):

- [Montmorency station entrance](https://commons.wikimedia.org/wiki/File:Montmorency_station_entrance,_October_13,_2021.jpg) by D. Benjamin Miller, CC0 (Canon EOS R5, 14 mm).
- [David Geffen Hall with fountain in the foreground](https://commons.wikimedia.org/wiki/File:David_Geffen_Hall_with_fountain_in_the_foreground,_March_14,_2024.jpg) by D. Benjamin Miller, CC0 (Canon EOS R5, 10 mm; trimmed slightly on Commons, so the tool uses 10.2 mm).
- [Liqeni Artificial i Tiranës 05](https://commons.wikimedia.org/wiki/File:Liqeni_Artificial_i_Tiran%C3%ABs_05_-_%C2%A9_Shk%C3%ABlzen_Rexha.jpg) by Shkelzen A. Rexha, CC0 (Canon EOS 5D Mark IV, 20 mm).

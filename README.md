# prospekt-site

The website for [Prospekt](https://apps.apple.com/app/id6760914468), the iPhone lens simulator, served by GitHub Pages from `main`.

It has four kinds of pages, in 16 languages (the app's own), all plain HTML that reads fine without JavaScript:

- `/`: what the app does, price, privacy, limits, an honest comparison, FAQ.
- `/lens-compare/`: a free lens comparison tool. Pick a body and focal lengths and see the frames over a photo (the sample, or your own; it never leaves the browser). Links are shareable: `/lens-compare/?body=fujifilm-x-t5&f=23,33,56`.
- `/cameras/` and `/cameras/<body>/`: focal length, full-frame equivalent and angle-of-view tables for every body in the app.
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
- Everything else at the root (`index.html`, `lens-compare/`, `cameras/`, `changelog/`, `<lang>/`, `sitemap.xml`, `robots.txt`, `llms.txt`) is generated. Edit the generator, not the output.

## Changing things

- **New camera in the app:** `make bodies`, add its mount to `data/mounts.json`, `make build`.
- **New app version:** add the notes to `CHANGELOG` in `gen/build.py` and the strings to every `i18n/*.json`.
- **Copy change:** edit `i18n/en.json`, then update the same key in every other language.
- **Custom domain:** add the DNS record first, then set the domain in the repo's Pages settings (a `CNAME` file), then change `BASE_URL` and rebuild. Doing it in the other order makes the github.io URL redirect to a host that doesn't resolve.

Sample photo: [Montmorency station entrance](https://commons.wikimedia.org/wiki/File:Montmorency_station_entrance,_October_13,_2021.jpg) by D. Benjamin Miller, CC0 (Canon EOS R5, 14 mm).

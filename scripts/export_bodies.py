"""Copies the app's camera list into data/bodies.json.

Usage: python3 scripts/export_bodies.py ../prospekt/Prospekt/Models/CameraBody.swift

The app's CameraBody.curated array is the source of truth. Run this after a
body is added to the app, then `make build`.
"""

import json
import os
import re
import sys

BODY = re.compile(
    r'CameraBody\(name:\s*"([^"]+)",\s*brand:\s*"([^"]+)",\s*cropFactor:\s*([0-9.]+)\)'
)


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def parse(swift_source):
    start = swift_source.index("= [", swift_source.index("static let curated"))
    end = swift_source.index("\n    ]", start)
    bodies = []
    for name, brand, crop in BODY.findall(swift_source[start:end]):
        bodies.append(
            {
                "slug": slugify("%s %s" % (brand, name)),
                "brand": brand,
                "name": name,
                "crop": float(crop),
            }
        )
    slugs = [b["slug"] for b in bodies]
    if len(set(slugs)) != len(slugs):
        raise ValueError("duplicate body slugs")
    return bodies


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    with open(argv[1], encoding="utf-8") as f:
        bodies = parse(f.read())
    out = os.path.join(os.path.dirname(__file__), "..", "data", "bodies.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(bodies, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print("wrote %d bodies" % len(bodies))


if __name__ == "__main__":
    main(sys.argv)

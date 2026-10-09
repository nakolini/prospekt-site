import json
import os
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
import lensmath as lm  # noqa: E402

JS = os.path.abspath(os.path.join(HERE, "..", "..", "assets", "lens-compare.js"))
CASES = [(f, c) for f in [14, 24, 35, 50, 85, 135, 300] for c in [0.79, 1.0, 1.5, 1.6, 2.0]]

SCRIPT = """
const m = require(%s);
const cases = %s;
console.log(JSON.stringify(cases.map(([f, c]) => [m.angles(f, c), m.frameInPhoto(f, c, 14, 1.5), m.frameInPhoto(f, c, 26, 0.75)])));
"""


@unittest.skipUnless(shutil.which("node"), "node not installed")
class JsParityTest(unittest.TestCase):
    def test_js_math_matches_python(self):
        out = subprocess.check_output(["node", "-e", SCRIPT % (json.dumps(JS), json.dumps(CASES))])
        for (focal, crop), (angles, frame, portrait) in zip(CASES, json.loads(out)):
            for a, b in zip(angles, lm.angles(focal, crop)):
                self.assertAlmostEqual(a, b, places=9)
            for a, b in zip(frame, lm.frame_in_photo(focal, crop, 14, 1.5)):
                self.assertAlmostEqual(a, b, places=9)
            for a, b in zip(portrait, lm.frame_in_photo(focal, crop, 26, 0.75)):
                self.assertAlmostEqual(a, b, places=9)


if __name__ == "__main__":
    unittest.main()


def jpeg_with_equivalent_focal(focal, little_endian=True):
    import struct
    end = "<" if little_endian else ">"
    tiff = (b"II" if little_endian else b"MM") + struct.pack(end + "HI", 42, 8)
    # IFD0 at 8: one entry, the Exif IFD pointer, then next-IFD offset 0.
    tiff += struct.pack(end + "H", 1) + struct.pack(end + "HHII", 0x8769, 4, 1, 26) + struct.pack(end + "I", 0)
    # Exif IFD at 26: FocalLengthIn35mmFilm, SHORT, padded to 4 bytes.
    tiff += struct.pack(end + "H", 1) + struct.pack(end + "HHIHH", 0xA405, 3, 1, focal, 0) + struct.pack(end + "I", 0)
    app1 = b"Exif\x00\x00" + tiff
    return b"\xff\xd8" + b"\xff\xe1" + struct.pack(">H", len(app1) + 2) + app1 + b"\xff\xd9"


EXIF_SCRIPT = """
const m = require(%s);
const read = (hex) => { const b = Buffer.from(hex, 'hex'); return m.exifEquivalentFocal(b.buffer.slice(b.byteOffset, b.byteOffset + b.length)); };
console.log(JSON.stringify(%s.map(read)));
"""


@unittest.skipUnless(shutil.which("node"), "node not installed")
class ExifTest(unittest.TestCase):
    def test_reads_equivalent_focal_both_byte_orders(self):
        samples = [jpeg_with_equivalent_focal(13).hex(), jpeg_with_equivalent_focal(77, False).hex(),
                   "ffd8ffd9", "89504e47"]
        out = subprocess.check_output(["node", "-e", EXIF_SCRIPT % (json.dumps(JS), json.dumps(samples))])
        self.assertEqual(json.loads(out), [13, 77, None, None])

import json
import os
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts"))
import export_bodies  # noqa: E402

SWIFT = '''
struct CameraBody {
    static let curated: [CameraBody] = [
        // Canon — Full Frame
        CameraBody(name: "R5 II", brand: "Canon", cropFactor: 1.0),
        // OM System — Micro Four Thirds
        CameraBody(name: "OM-1 II", brand: "OM System", cropFactor: 2.0),
    ]
}
enum Other { static let x = [CameraBody(name: "Nope", brand: "X", cropFactor: 1.0)] }
'''


class ExportBodiesTest(unittest.TestCase):
    def test_parses_only_the_curated_array(self):
        bodies = export_bodies.parse(SWIFT)
        self.assertEqual(bodies, [
            {"slug": "canon-r5-ii", "brand": "Canon", "name": "R5 II", "crop": 1.0},
            {"slug": "om-system-om-1-ii", "brand": "OM System", "name": "OM-1 II", "crop": 2.0},
        ])

    def test_committed_data_is_complete(self):
        root = os.path.join(HERE, "..", "..")
        with open(os.path.join(root, "data", "bodies.json")) as f:
            bodies = json.load(f)
        with open(os.path.join(root, "data", "mounts.json")) as f:
            mounts = json.load(f)
        self.assertEqual(len(bodies), 59)
        self.assertEqual(sorted(b["slug"] for b in bodies), sorted(mounts))
        for body in bodies:
            self.assertIn(body["crop"], [0.79, 1.0, 1.5, 1.6, 2.0])


if __name__ == "__main__":
    unittest.main()

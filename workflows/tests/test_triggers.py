"""The trigger registry must stay honest: 9 triggers, and every module it
points at must actually exist."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from workflows.triggers import TRIGGERS, describe


class TriggerRegistry(unittest.TestCase):
    def test_nine_triggers_numbered_one_to_nine(self):
        self.assertEqual([t.number for t in TRIGGERS], list(range(1, 10)))

    def test_kinds_match_the_docs(self):
        by_number = {t.number: t for t in TRIGGERS}
        self.assertEqual(by_number[7].kind, "event")
        self.assertEqual(by_number[8].kind, "scheduled")
        self.assertEqual(by_number[9].kind, "scheduled")
        self.assertEqual({t.kind for t in TRIGGERS}, {"event", "scheduled"})

    def test_every_implemented_in_points_at_a_real_file(self):
        for trig in TRIGGERS:
            # "path/to/file.py::symbol → other/file.py" -- pull out every *.py token
            tokens = trig.implemented_in.replace("→", " ").replace("::", " ").split()
            paths = [tok.split("::")[0] for tok in tokens if tok.endswith(".py")]
            self.assertTrue(paths, f"trigger {trig.number} names no source file")
            for rel in paths:
                self.assertTrue((ROOT / rel).is_file(), f"trigger {trig.number}: missing {rel}")

    def test_describe_is_non_empty(self):
        text = describe()
        self.assertIn("[8]", text)
        self.assertIn("[9]", text)


if __name__ == "__main__":
    unittest.main()

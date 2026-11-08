import unittest
from parser import parse_episode, stamp, ticks

SAMPLE = """EPISODE LOGLINE: A stranger appears.
--- SCRIPT START ---
SCENE 01
Scene end: 00:30.00
**CAMERA:**
Start: (00:00.00) | End: (00:05.00)
Wide shot.
**MIRA (Angry):**
Start: (00:01.10) | End: (00:04.20)
"Who sent you?"
**ACTION:**
invalid
**SOUND FX:**
Start: (00:29.00) | End: (00:30.00)
Sting.
--- SCRIPT END ---"""


class ParserTests(unittest.TestCase):
    def test_overlapping_tracks_and_malformed_block(self):
        with self.assertLogs("parser", level="WARNING") as logs:
            episode = parse_episode(SAMPLE.replace("\n", "\r\n"), 7)
        self.assertIn("malformed ACTION", logs.output[0])
        self.assertEqual([event.type for event in episode.events],
                         ["CAMERA", "DIALOGUE", "SOUND FX"])
        line = episode.events[1]
        self.assertEqual((line.scene, line.speaker, line.emotion), (1, "MIRA", "Angry"))
        self.assertEqual((line.start_sec, line.end_sec), (1.1, 4.2))
        self.assertEqual(episode.end, 3000)

    def test_timestamp_round_trip(self):
        self.assertEqual(stamp(ticks("02:09.7")), "02:09.70")

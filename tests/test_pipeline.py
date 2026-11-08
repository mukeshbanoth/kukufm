import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from candidates import Segment, Timeline, checks, score_candidate
from find_promos import run
from llm_judge import Judge, LLMProvider, parse_response
from parser import parse_episode
from test_parser import SAMPLE
from validate import validate

SCRIPT = SAMPLE.replace('"Who sent you?"', '"Who sent the guards after us?"').replace(
    "**SOUND FX:**", '''**MIRA (Frightened):**
Start: (00:25.00) | End: (00:27.00)
"Are they coming back for us?"
**SOUND FX:**''')


class FakeProvider(LLMProvider):
    identity = ("test",)
    model = "test"

    def __init__(self):
        self.stats = Counter()
        self.prompts = []

    def complete(self, prompt):
        self.prompts.append(prompt)
        if "Episode context:" in prompt:
            row = {"id": "1", "scores": dict.fromkeys(
                ["hook", "cliffhanger", "standalone", "emotion", "retention"], 8),
                   "why": "The opening asks who sent the guards and the ending asks if they will return.",
                   "hook": {"episode": 7, "start": "00:01.10", "end": "00:04.20",
                            "quote": "Who sent the guards after us?"},
                   "cliffhanger": {"episode": 7, "start": "00:25.00", "end": "00:27.00",
                                  "quote": "Are they coming back for us?"}}
        else:
            row = {"id": "1", "understandable": True, "reason": "Someone sent guards.",
                   "unresolved": "Will the guards return?"}
        return json.dumps({"items": [row]})


class PipelineTests(unittest.TestCase):
    def test_boundary_inside_dialogue_and_invented_quote(self):
        script = SCRIPT.replace("End: (00:05.00)", "End: (00:02.50)")
        timelines = {7: Timeline(parse_episode(script, 7))}
        cut = (Segment(7, 0, 3000),)
        candidate = score_candidate(cut, timelines, "episode ending")
        fake = {**candidate.hook, "quote": "I am the queen of the moon."}
        self.assertFalse(checks(cut, fake, candidate.cliffhanger, timelines)["opening_evidence"])
        unsafe = (Segment(7, 250, 3000),)
        rules = checks(unsafe, candidate.hook, candidate.cliffhanger, timelines)
        self.assertTrue(rules["real_boundaries"])
        self.assertFalse(rules["no_mid_dialogue"])

    def test_two_pass_pipeline_and_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            episodes = root / "show"
            episodes.mkdir()
            (episodes / "episode-007-test.txt").write_text(SCRIPT, encoding="utf-8")
            provider = FakeProvider()
            judge = Judge(provider, root / "cache")
            with patch("llm_judge.make_judge", return_value=(judge, "Test provider")):
                run(episodes, root / "out", "gemini", budget=1)
                results = run(episodes, root / "out", "gemini", budget=1)
            self.assertEqual(len(provider.prompts), 2)
            self.assertIn("A stranger appears.", provider.prompts[0])
            self.assertNotIn("A stranger appears.", provider.prompts[1])
            self.assertNotIn("00:01.10", provider.prompts[1])
            rows, stats = results["show"]
            self.assertEqual(rows[0]["scoring_source"], "llm+heuristic")
            self.assertEqual(stats["cache_hits"], 2)
            data = json.loads((root / "out/promos.json").read_text(encoding="utf-8"))
            self.assertTrue(all(validate(data, {7: parse_episode(SCRIPT, 7)})[0].values()))

    def test_strict_schema_rejects_missing_ids(self):
        with self.assertRaises(ValueError):
            parse_response('{"items": []}', {"1"}, set(), cold=True)

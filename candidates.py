"""Generate safe windows and attach inspectable screenplay evidence."""
import re
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache

from parser import stamp, ticks

HOOKS = {
    "physical danger": r"\b(slap\w*|strikes?|stabs?|shoot\w*|blade|dagger|blood|sword|arrows?|poison\w*|lunges?|fires?|explodes?)\b",
    "threat": r"\b(kill\w*|die|death|execute\w*|prison|arrest\w*|guards|treason|revenge|or else)\b",
    "reveal": r"\b(truth|secret|betray\w*|lied|liar|identity|impostor|real father|pregnant|marry\w*|marriage|husband|wife)\b",
    "humiliation": r"\b(shame\w*|humiliat\w*|beg\w*|kneel\w*|worthless|mock\w*|laugh\w*|disgrace\w*|filth)\b",
}
EMOTION = re.compile(r"angry|rage|fear|furious|shock|horror|desperate|panic|outrage|terror|cold|threat", re.I)
STING = re.compile(r"sting|swell|cliffhanger|cut to black|smash to black", re.I)
RESOLUTION = re.compile(r"\b(safe now|it's over|we won|forgive you|all right now|thank you|finally relax\w*)\b", re.I)
DEPENDENT = re.compile(r"^(because |of course |and |but |so |yes\b|no\b|what\?|why\?|he |she |they |it |that |this )", re.I)
WORDS = re.compile(r"\w+", re.UNICODE)
PATTERNS = {key: re.compile(pattern, re.I) for key, pattern in HOOKS.items()}


@dataclass(frozen=True, order=True)
class Segment:
    episode: int
    start: int
    end: int

    def export(self):
        return {"episode": self.episode, "start": stamp(self.start), "end": stamp(self.end)}


def event_text(event):
    return event.text.strip('“”"')


def evidence(event):
    return {"episode": event.episode, "start": stamp(event.start), "end": stamp(event.end),
            "speaker": event.speaker, "quote": event_text(event)}


def overlap(left, right):
    shared = sum(max(0, min(a.end, b.end) - max(a.start, b.start))
                 for a in left for b in right if a.episode == b.episode)
    return shared / min(duration(left), duration(right))


def duration(segments):
    return sum(segment.end - segment.start for segment in segments)


class Timeline:
    def __init__(self, episode):
        self.episode = episode
        self.events = episode.events
        dialogue = [e for e in self.events if e.type == "DIALOGUE"]
        boundaries = sorted({time for event in self.events for time in (event.start, event.end)})
        self.boundaries = set(boundaries)
        self.safe = [time for time in boundaries if not any(e.start < time < e.end for e in dialogue)]

    def clip(self, segment):
        return [e for e in self.events if e.start < segment.end and e.end > segment.start]

    def ending(self):
        return self.safe[-1] if self.safe else 0


@dataclass
class Candidate:
    segments: tuple
    tracks: list
    kind: str
    scores: dict
    hook: dict
    cliffhanger: dict
    features: dict
    speaker: str

    @property
    def id(self):
        return "-".join(f"e{s.episode:03d}_{s.start}_{s.end}" for s in self.segments)


@lru_cache(maxsize=8192)
def hook_strength(event):
    quote = event_text(event)
    kinds = [key for key, pattern in PATTERNS.items() if pattern.search(quote)]
    if re.search(r"\b(no one should die|nobody should die|did not poison|didn't poison)\b", quote, re.I):
        kinds = [key for key in kinds if key not in {"threat", "physical danger"}]
    kind = kinds[0] if kinds else ("question" if "?" in quote else "confrontation")
    value = 3.0 + 2.1 * bool(kinds) + 0.6 * (len(kinds) > 1)
    value += 0.9 * bool(EMOTION.search(event.emotion)) + 0.8 * ("!" in quote) + 0.6 * ("?" in quote)
    if event.type == "DIALOGUE":
        value += 0.8 - 1.4 * (len(WORDS.findall(quote)) < 4)
        value -= 0.8 * bool(DEPENDENT.search(quote))
    else:
        value -= 0.5
    return value, kind


@lru_cache(maxsize=32768)
def ending_strength(event, end):
    quote = event_text(event)
    score = 3.4 + 2.0 * ("?" in quote) + 1.1 * ("..." in quote or "…" in quote)
    score += 1.4 * any(PATTERNS[k].search(quote) for k in ("threat", "reveal", "physical danger"))
    score += 0.6 * bool(EMOTION.search(event.emotion)) + 0.5 * ("!" in quote)
    score -= 3.0 * bool(RESOLUTION.search(quote)) + 0.28 * ((end - event.end) / 100)
    if event.type == "CAMERA":
        score -= 1.2
    return score


def score_candidate(segments, timelines, kind):
    tracks = [timelines[s.episode].clip(s) for s in segments]
    if not all(tracks):
        return None
    first, last = segments[0], segments[-1]
    opening = [e for e in tracks[0] if first.start <= e.start < first.start + 300
               and e.end <= first.end and e.type != "SOUND FX"]
    ending = [e for e in tracks[-1] if last.start <= e.start and last.end - 600 < e.end <= last.end
              and e.type != "SOUND FX"]
    if not opening or not ending:
        return None

    def opening_value(event):
        return hook_strength(event)[0] - (event.start - first.start) / 250

    hook = max(opening, key=opening_value)
    cliff = max(ending, key=lambda event: ending_strength(event, last.end))
    lines = [e for track in tracks for e in track if e.type == "DIALOGUE"]
    if lines and lines[0].start < first.start + 100 and event_text(lines[0]).startswith(("...", "…")):
        return None
    density = len(lines) / (duration(segments) / 100)
    late = [e for e in tracks[-1] if last.end - 450 < e.end <= last.end]
    sting = any(STING.search(e.text) for e in late)
    resolved = any(e.type == "DIALOGUE" and RESOLUTION.search(event_text(e)) for e in late)
    recent = [e for e in tracks[-1] if last.end - 1200 < e.end <= last.end]
    payoff = any(e.type in {"CAMERA", "ACTION"} and re.search(r"\btriumphant\w*\b", e.text, re.I)
                 for e in recent)
    reaction_only = cliff.type == "DIALOGUE" and len(WORDS.findall(cliff.text)) <= 2
    resolved = resolved or (payoff and reaction_only)
    context_gap = bool(lines and DEPENDENT.search(re.sub(r"^\[[^\]]+\]\s*", "", event_text(lines[0]))))
    clarity = 5.1 + min(2.4, density * 8) - 1.1 * context_gap - 0.9 * (len(segments) > 1)
    energy = 3.8 + min(4.0, sum(bool(EMOTION.search(e.emotion)) for e in lines) * 0.65)
    hook_score = opening_value(hook)
    cliff_score = ending_strength(cliff, last.end) + 0.9 * sting - 1.2 * resolved
    scores = dict(hook=hook_score, cliffhanger=cliff_score, standalone=clarity, emotion=energy,
                  retention=(hook_score + cliff_score + clarity) / 3)
    scores = {key: round(max(0, min(10, value)), 3) for key, value in scores.items()}
    speaker = hook.speaker or (Counter(e.speaker for e in lines).most_common(1)[0][0] if lines else "")
    return Candidate(segments, tracks, kind, scores, {**evidence(hook), "type": hook_strength(hook)[1]},
                     evidence(cliff), {"dialogue_per_second": round(density, 3),
                                       "ending_cue": sting, "resolution_cue": resolved,
                                       "context_gap": context_gap}, speaker)


def generate(timelines):
    result = []
    for episode, timeline in timelines.items():
        for i, start in enumerate(timeline.safe):
            for end in timeline.safe[i + 1:]:
                if end - start > 6000:
                    break
                if end - start < 2000:
                    continue
                kind = "episode ending" if end == timeline.ending() else "continuous"
                candidate = score_candidate((Segment(episode, start, end),), timelines, kind)
                if candidate:
                    result.append(candidate)
        following = timelines.get(episode + 1)
        if not following or not timeline.safe or not following.safe:
            continue
        tail, head = timeline.ending(), following.safe[0]
        for start in timeline.safe:
            if not 1200 <= tail - start <= 3600:
                continue
            first = Segment(episode, start, tail)
            left_speakers = {e.speaker for e in timeline.clip(first) if e.speaker}
            for end in following.safe:
                if not 800 <= end - head <= 2600:
                    continue
                second = Segment(episode + 1, head, end)
                if not 2000 <= duration((first, second)) <= 6000:
                    continue
                right_speakers = {e.speaker for e in following.clip(second) if e.speaker}
                if not left_speakers & right_speakers:
                    continue
                candidate = score_candidate((first, second), timelines, "adjacent episode join")
                if candidate:
                    result.append(candidate)
    return result


def normalized(text):
    return " ".join(WORDS.findall(text.casefold()))


def matching_event(item, segments, timelines, hook=False):
    try:
        start, end = ticks(item["start"]), ticks(item["end"])
        quote = normalized(item["quote"])
        if not quote:
            return None
        for segment in segments[:1] if hook else segments[-1:]:
            if item["episode"] != segment.episode or not segment.start <= start < end <= segment.end:
                continue
            if hook and start >= segment.start + 300:
                continue
            if not hook and end <= segment.end - 600:
                continue
            for event in timelines[segment.episode].clip(segment):
                if (event.start, event.end) != (start, end):
                    continue
                original = normalized(event_text(event))
                matched = quote == original or (len(quote) >= 18 and (
                    f" {quote} " in f" {original} " or
                    SequenceMatcher(None, quote, original).ratio() >= 0.91))
                if matched:
                    return event
    except (KeyError, TypeError, ValueError, AttributeError):
        return None
    return None


def checks(segments, hook, cliff, timelines):
    known = bool(segments) and all(s.episode in timelines for s in segments)
    return {
        "duration_20_60": 2000 <= duration(segments) <= 6000,
        "chronological": bool(segments) and all(
            s.start < s.end for s in segments) and all(
            a.episode < b.episode or (a.episode == b.episode and a.end <= b.start)
            for a, b in zip(segments, segments[1:])),
        "real_boundaries": known and all(s.start in timelines[s.episode].boundaries and
                                         s.end in timelines[s.episode].boundaries for s in segments),
        "no_mid_dialogue": known and all(s.start in timelines[s.episode].safe and
                                         s.end in timelines[s.episode].safe for s in segments),
        "opening_evidence": known and matching_event(hook, segments, timelines, hook=True) is not None,
        "ending_evidence": known and matching_event(cliff, segments, timelines) is not None,
    }

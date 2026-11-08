"""Check exported cuts against the scripts and optionally compare two rankings."""
import argparse
import json
from collections import Counter
from pathlib import Path

from candidates import Segment, Timeline, checks, duration, overlap
from parser import load_shows, ticks


def segments(row):
    return tuple(Segment(s["episode"], ticks(s["start"]), ticks(s["end"])) for s in row["segments"])


def validate(data, episodes):
    timelines = {n: Timeline(episode) for n, episode in episodes.items()}
    rows = data["promos"]
    cuts = [segments(row) for row in rows]
    participation = Counter(n for cut in cuts for n in {s.episode for s in cut})
    results = []
    for i, (row, cut) in enumerate(zip(rows, cuts)):
        rules = checks(cut, row["hook"], row["cliffhanger"], timelines)
        rules["reported_duration"] = round(row["total_duration"] * 100) == duration(cut)
        rules["overlap_cap"] = duration(cut) > 0 and all(
            overlap(cut, other) <= data["config"]["max_overlap"]
            for j, other in enumerate(cuts) if i != j and duration(other) > 0)
        rules["episode_cap"] = all(participation[s.episode] <= data["config"]["episode_cap"] for s in cut)
        results.append(rules)
    return results


def agreement(offline, model):
    if not any(row["scoring_source"] == "llm+heuristic" for row in model):
        return "Not measured. The comparison export contains no model-judged ranked promos."
    left, right = [segments(r) for r in offline], [segments(r) for r in model]
    exact = len(set(left) & set(right))
    union = len(set(left) | set(right))
    near = sum(any(overlap(cut, other) >= .75 for other in left) for cut in right)
    return (f"Exact cut Jaccard {exact}/{union}. Model-list cuts matching >=75% of the shorter "
            f"cut in the offline list {near}/{len(right)}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--promos", default="outputs/promos.json")
    parser.add_argument("--compare", help="Optional second JSON export from model mode")
    args = parser.parse_args()
    data = json.loads(Path(args.promos).read_text(encoding="utf-8-sig"))
    shows = load_shows(args.input)
    episodes = shows.get(data["show"])
    if episodes is None:
        if len(shows) != 1:
            parser.error("Show name does not identify a unique input")
        episodes = next(iter(shows.values()))
    results = validate(data, episodes)
    print(f"{len(results)} ranked promos")
    if results:
        for rule in results[0]:
            passed = sum(row[rule] for row in results)
            print(f"{rule}: {passed}/{len(results)} ({100 * passed / len(results):.1f}%)")
    if args.compare:
        model = json.loads(Path(args.compare).read_text(encoding="utf-8-sig"))
        if model["show"] != data["show"]:
            parser.error("Comparison exports belong to different shows")
        print(agreement(data["promos"], model["promos"]))
    else:
        print("Offline/model agreement not measured. Provide --compare with a model export.")
    raise SystemExit(0 if results and all(all(row.values()) for row in results) else 1)


if __name__ == "__main__":
    main()

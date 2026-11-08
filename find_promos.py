"""Run the same pipeline from the command line and the local app."""
import argparse
import json
import logging
from collections import Counter
from pathlib import Path
from time import perf_counter

from candidates import Timeline, generate
from parser import load_shows
from ranker import rank

ROOT = Path(__file__).resolve().parent


def run(source, out, provider="gemini", model=None, top=15, budget=12,
        base_url=None, config_path=ROOT / "config.json", cache_dir=ROOT / ".cache"):
    from report import write_reports
    from llm_judge import make_judge

    if top < 1 or budget < 0:
        raise ValueError("Top must be positive and budget must be nonnegative")
    start = perf_counter()
    config = json.loads(Path(config_path).read_text(encoding="utf-8-sig"))
    shows = load_shows(source)
    judge, status = make_judge(provider, model, base_url, cache_dir)
    results = {}
    for index, (show, episodes) in enumerate(shows.items(), 1):
        began = perf_counter()
        timelines = {n: Timeline(episode) for n, episode in episodes.items()}
        candidates = generate(timelines)
        judgments, usage = judge.evaluate(candidates, timelines, config, budget) if judge else ({}, {})
        rows = rank(candidates, judgments, timelines, config, top)
        counts = Counter(e.type for episode in episodes.values() for e in episode.events)
        stats = {"requested_provider": provider, "provider_status": status, "episodes": len(episodes),
                 "events": dict(counts), "candidates": len(candidates),
                 "candidate_kinds": dict(Counter(c.kind for c in candidates)),
                 "returned": len(rows), "dual_judged_candidates": len(judgments),
                 "ranked_llm": sum(r["scoring_source"] == "llm+heuristic" for r in rows),
                 "runtime_seconds": round(perf_counter() - began, 2),
                 "http_attempts": 0, "input_tokens_est": 0, "output_tokens_est": 0,
                 "cache_hits": 0, "schema_failures": 0, "evidence_failures": 0,
                 "provider_errors": [], "paid_equivalent_usd_est": 0.0, **usage}
        target = Path(out) if len(shows) == 1 else Path(out) / f"show-{index:02d}"
        write_reports(target, show, rows, stats, config)
        results[show] = (rows, stats)
    logging.info("Finished %d show(s) in %.2fs", len(shows), perf_counter() - start)
    return results


def main():
    from dotenv import load_dotenv
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Episode directory or ZIP")
    parser.add_argument("--out", default="outputs")
    parser.add_argument("--provider", choices=["gemini", "openai", "offline"], default="gemini")
    parser.add_argument("--model")
    parser.add_argument("--base-url")
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--budget", type=int, default=12, help="Maximum candidates sent to each judging pass per show")
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument("--cache-dir", type=Path, default=ROOT / ".cache")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        results = run(args.input, args.out, args.provider, args.model, args.top, args.budget,
                      args.base_url, args.config, args.cache_dir)
    except (OSError, ValueError) as error:
        parser.exit(2, f"{error}\n")
    for show, (rows, stats) in results.items():
        print(f"{show}: {stats['episodes']} episodes, {len(rows)} promos. {stats['provider_status']}")


if __name__ == "__main__":
    main()

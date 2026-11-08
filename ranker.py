"""Select cuts with an explicit overlap cap and soft diversity penalties."""
from collections import Counter

from candidates import checks, duration, overlap


def weighted(scores, config):
    return sum(value * scores[key] for key, value in config["weights"].items())


def rank(candidates, judgments, timelines, config, top):
    pool = []
    for candidate in candidates:
        verdict = judgments.get(candidate.id)
        hook, cliff = candidate.hook, candidate.cliffhanger
        scores = candidate.scores.copy()
        cold = {"source": "heuristic", "understandable": None,
                "reason": "Opening may depend on earlier context." if candidate.features["context_gap"]
                else "Opening has no simple context warning. Editor review pending.", "unresolved": ""}
        why = (f"{hook['type'].capitalize()} cue opens the cut. "
               f"The ending {'has a scripted sting' if candidate.features['ending_cue'] else 'has a late dramatic beat'}.")
        confidence = "low"
        if verdict:
            hook, cliff, cold, why = (verdict[key] for key in ("hook", "cliffhanger", "cold", "why"))
            weight = config["model_weight"]
            scores = {key: round((1 - weight) * value + weight * verdict["scores"][key], 3)
                      for key, value in scores.items()}
            confidence = "medium" if cold["understandable"] else "low"
        if not all(checks(candidate.segments, hook, cliff, timelines).values()):
            continue
        base = weighted(scores, config)
        if cold["understandable"] is False:
            base -= 1.75
        if cold["source"] == "llm" and cold["unresolved"].strip().casefold().rstrip(".") == "none":
            base -= 1.25
            confidence = "low"
        if len(candidate.segments) > 1:
            base -= config["join_penalty"]
        if candidate.features["resolution_cue"]:
            base -= 0.7
        pool.append((candidate, base, scores, hook, cliff, cold, why, confidence))

    picked, rows = [], []
    episodes, hooks, speakers = Counter(), Counter(), Counter()
    for position in range(1, top + 1):
        def adjusted(item):
            c, base, *_ = item
            return (base - hooks[c.hook["type"]] * config["hook_repeat_penalty"]
                    - speakers[c.speaker] * config["speaker_repeat_penalty"])

        pool = [item for item in pool if all(episodes[s.episode] < config["episode_cap"]
                                             for s in item[0].segments)
                and all(overlap(item[0].segments, prior.segments) <= config["max_overlap"]
                        for prior in picked)]
        if not pool:
            break
        winner = max(pool, key=lambda item: (adjusted(item), item[1], item[0].id))
        c, base, scores, hook, cliff, cold, why, confidence = winner
        rows.append({"rank": position, "promo_id": c.id, "kind": c.kind,
                     "segments": [s.export() for s in c.segments],
                     "total_duration": duration(c.segments) / 100, "hook": hook, "cliffhanger": cliff,
                     "why": why, "scores": scores, "standalone": cold, "confidence": confidence,
                     "base_score": round(base, 3), "selection_score": round(adjusted(winner), 3),
                     "rank_reason": f"Best eligible adjusted score at pick {position}. "
                                    f"Base {base:.2f}, repetition penalty {base-adjusted(winner):.2f}.",
                     "features": c.features, "scoring_source": "llm+heuristic" if c.id in judgments else "heuristic"})
        pool.remove(winner)
        picked.append(c)
        episodes.update({s.episode for s in c.segments})
        hooks[c.hook["type"]] += 1
        if c.speaker:
            speakers[c.speaker] += 1
    return rows

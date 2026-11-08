"""Write raw rankings and an editor's review queue."""
import csv
import json
from pathlib import Path


def write_text(path, value):
    Path(path).write_text(value, encoding="utf-8")


def segments_text(row):
    return " + ".join(f"E{s['episode']} {s['start']}–{s['end']}" for s in row["segments"])


def write_reports(out, show, rows, stats, config):
    out.mkdir(parents=True, exist_ok=True)
    write_text(out / "promos.json", json.dumps(
        {"show": show, "stats": stats, "config": config, "promos": rows},
        indent=2, ensure_ascii=False) + "\n")
    with (out / "promos.csv").open("w", encoding="utf-8-sig", newline="") as file:
        fields = ["rank", "promo_id", "segments", "total_duration", "hook_type", "hook", "cliffhanger",
                  "why", "standalone", "confidence", "scoring_source", "base_score", "selection_score",
                  "hook_score", "cliffhanger_score", "standalone_score", "emotion_score", "retention_score"]
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow({**{key: r[key] for key in fields if key in r},
                             **{key + "_score": val for key, val in r["scores"].items()},
                             "segments": json.dumps(r["segments"]),
                             "hook_type": r["hook"]["type"], "hook": r["hook"]["quote"],
                             "cliffhanger": r["cliffhanger"]["quote"],
                             "standalone": json.dumps(r["standalone"], ensure_ascii=False)})
    with (out / "review.csv").open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["rank", "promo_id", "segments", "hook ok", "cliffhanger ok", "standalone ok", "notes"])
        for row in rows:
            writer.writerow([row["rank"], row["promo_id"], segments_text(row), "", "", "", ""])
    lines = [f"# Ranked promos for {show}", "", stats["provider_status"], "",
             "## Top five to post first", ""]
    for r in rows[:5]:
        lines.append(f"{r['rank']}. **{segments_text(r)}.** {r['why']} {r['rank_reason']}")
    lines.extend(["", "## All ranked cuts", ""])
    for r in rows:
        lines.extend([
            f"### {r['rank']}. {segments_text(r)}", "",
            f"{r['total_duration']:.2f} seconds · {r['kind']} · {r['confidence']} confidence", "",
            f"- Hook ({r['hook']['type']}, E{r['hook']['episode']} {r['hook']['start']}) — {r['hook']['quote']}",
            f"- Ending (E{r['cliffhanger']['episode']} {r['cliffhanger']['start']}) — {r['cliffhanger']['quote']}",
            f"- Why it works — {r['why']}",
            f"- Standalone check — {r['standalone']['reason']}",
            f"- Rank — {r['rank_reason']}", "",
        ])
    write_text(out / "promos_ranked.md", "\n".join(lines))
    write_text(out / "run_log.txt", "\n".join(f"{key} = {value}" for key, value in stats.items()) + "\n")

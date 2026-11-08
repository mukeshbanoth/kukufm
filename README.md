# Find the promos

This local tool turns timestamped microdrama screenplays into a ranked cut list. It takes episode text as input and returns edit points, source evidence and an editor review sheet.

## Set up and run

Use Python 3.11 or newer. From this folder, run these PowerShell commands.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe find_promos.py --input "C:\path\to\show.zip" --provider offline --top 15 --out outputs
.\.venv\Scripts\python.exe validate.py --input "C:\path\to\show.zip" --promos outputs/promos.json
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

On macOS or Linux, use `.venv/bin/python`. A directory works in place of the ZIP. Place UTF-8 episode files named `episode-NNN*.txt` directly in a show folder or group several show folders under the input root. Multiple shows get separate numbered output directories. The app accepts an archive upload or a local directory path and uses the same pipeline.

## Model mode

Copy `.env.example` to `.env` and set `GEMINI_API_KEY` to your [Google AI Studio key](https://aistudio.google.com/app/apikey). Use a project with free quota and check its [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits). Run the following commands.

```powershell
python find_promos.py --input "C:\path\to\show.zip" --provider gemini --top 15 --out outputs-gemini
python validate.py --input "C:\path\to\show.zip" --promos outputs/promos.json --compare outputs-gemini/promos.json
```

Gemini is the CLI default. The app starts in offline mode so opening it is enough to prepare a no-key demo. The default model is `gemini-3.1-flash-lite`. For a different endpoint, set `OPENAI_API_KEY`, `OPENAI_BASE_URL` (include the API version path if required) and `OPENAI_MODEL`, then use `--provider openai`. You can override the model and base URL with `--model` and `--base-url`. The endpoint should implement chat completions with a string response. Without credentials, the tool labels the run as a fallback. The run log counts model coverage, schema failures, evidence failures, HTTP retries and cache hits.

## What the code checks

- `parser.py` reads timecodes as integer centiseconds. Dialogue can overlap camera or action. Malformed blocks are logged and skipped.
- `candidates.py` enumerates windows and tests cuts at episode endings. A join uses the tail and opening of adjacent episodes and requires a shared speaking character. This is a simple continuity screen. The offline features include opening action or dialogue, questions, exclamations, emotion tags, dialogue density, ending stings and resolution cues.
- `llm_judge.py` scores a shortlist using sampled timestamped dialogue, episode loglines and continuity notes. A separate cold pass reads only clip text. The judge scores proposed cuts from code. Model evidence must match a source event at exact times. A close text match can recover a small transcription variation, and the output always uses the original source text.
- `ranker.py` uses the weights in `config.json`: hook 28%, cliffhanger 30%, standalone 23%, emotion 8% and retention 11%. If both model passes return usable evidence, the weighted criteria are 70% model and 30% heuristic. Failed cold checks lose 1.75 points. It also penalizes joins, resolution cues, and repeated hook labels and speakers. Two promos per episode and at most 45% overlap of the shorter clip are hard limits.
- `report.py` writes JSON, CSV, a ranked Markdown report, a run log and the blank review sheet. `validate.py` checks timestamp rules and source evidence independently of the exported scores, then optionally compares two rankings. `outputs/quality_report.md` records the ten screenplay spot checks from the supplied pack.

## Cost and throughput

The default budget judges up to 12 clips per show in groups of four. A clean uncached run uses at most six requests, with extra calls possible on retries. At one request every 15 seconds, the sixth request starts at least 75 seconds after the first. If the project has 20 requests per day and 4 per minute, a planning ceiling is 21 whole shows per week when three shows finish each day. This example assumes the quota is dedicated and calls succeed. Use a smaller `--budget` for a demo.

As a planning example, 25,000 input and 3,000 output tokens per 50-episode show average 500 input and 60 output tokens per episode. That is about $0.011 per show or $0.00022 per episode at the published paid standard rate for this model. These figures are assumptions. The offline run used zero API tokens. The log uses provider token counts where returned and character-based estimates otherwise. [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)

A local cache stores schema-valid responses by provider, model and prompt. Keep it private because cached judgments can quote the script. The current system uses rules for pre-filtering. At higher volume I would compare a cheap model for a wider first pass and spend a stronger model's budget on finalists. An editor still watches the top clips against footage to catch slow hooks, closures, spoilers and awkward joins.

The input ZIP, extracted scripts, cache and output folders are ignored by Git. The raw outputs contain excerpts and are for the assignment review. Run the Streamlit app locally when reviewing this pack.

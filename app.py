"""Local editor preview. Start with python -m streamlit run app.py."""
from pathlib import Path
from tempfile import TemporaryDirectory

import streamlit as st
from dotenv import load_dotenv

from find_promos import run
from report import segments_text

st.set_page_config(page_title="Find the promos", page_icon=":material/movie:")
load_dotenv()
st.title("Find the promos")
st.caption("Rank screenplay cuts for an editor. Each result links a hook and ending to episode timecodes.")

with st.form("run"):
    upload = st.file_uploader("Screenplay ZIP", type=["zip"], max_upload_size=50)
    path = st.text_input("Or enter a local episode folder or ZIP path")
    left, right = st.columns(2)
    provider = left.selectbox("Provider", ["offline", "gemini", "openai"])
    top = right.number_input("Maximum promos per show", min_value=1, max_value=50, value=15)
    model = st.text_input("Model override")
    submitted = st.form_submit_button("Find promos", type="primary")

if submitted:
    st.session_state.pop("promo_results", None)
    if not upload and not path.strip():
        st.error("Upload a ZIP or enter a path.")
    else:
        try:
            with TemporaryDirectory() as directory, st.spinner("Reading screenplays and ranking cuts…"):
                temp = Path(directory)
                source = Path(path.strip().strip('"')).expanduser()
                if upload:
                    source = temp / "upload.zip"
                    source.write_bytes(upload.getbuffer())
                out = temp / "outputs"
                results = run(source, out, provider, model.strip() or None, int(top))
                downloads = [p.read_bytes() for p in sorted(out.rglob("promos.json"))]
                st.session_state["promo_results"] = (results, downloads)
        except (OSError, ValueError) as error:
            st.error(str(error))

if "promo_results" in st.session_state:
    results, downloads = st.session_state["promo_results"]
    show = st.selectbox("Show", list(results))
    rows, stats = results[show]
    st.caption(f"{stats['episodes']} episodes · {stats['candidates']:,} candidates · {len(rows)} promos")
    st.caption(stats["provider_status"])
    if stats.get("provider_errors"):
        st.warning("Model calls stopped. Remaining candidates use heuristic scores.")
    st.download_button("Download ranked JSON", downloads[list(results).index(show)],
                       file_name="promos.json", mime="application/json")
    if not rows:
        st.info("No eligible 20–60 second cuts were found.")
    for row in rows:
        with st.expander(f"#{row['rank']} · {segments_text(row)}", expanded=row["rank"] == 1):
            st.caption(f"{row['total_duration']:.2f} seconds · {row['scoring_source']} · {row['confidence']} confidence")
            st.text(f"Hook ({row['hook']['type']}) · {row['hook']['start']}")
            st.write(row["hook"]["quote"])
            st.text(f"Ending · {row['cliffhanger']['start']}")
            st.write(row["cliffhanger"]["quote"])
            st.write(row["why"])
            st.caption(row["standalone"]["reason"])
            st.caption(row["rank_reason"])

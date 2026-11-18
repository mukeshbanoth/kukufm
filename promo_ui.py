"""Shared editor interface for local and public Streamlit apps."""
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import zipfile

import streamlit as st
from dotenv import load_dotenv

from find_promos import run
from report import segments_text

ROOT = Path(__file__).resolve().parent


def render_app(public=False):
    st.set_page_config(page_title="Kuku · Promo finder", page_icon=":material/movie:", layout="wide")
    if not public:
        load_dotenv()

    with st.sidebar:
        st.title(":material/movie: Kuku")
        st.caption("PROMO FINDER")
        st.badge("Public demo" if public else "Editor workspace", icon=":material/movie:", color="violet")
        st.write("Find the scene worth sharing.")
        st.markdown("**Your workflow**")
        st.markdown(":violet[**01**]  Add a screenplay")
        st.markdown(":blue[**02**]  Generate your shortlist")
        st.markdown(":green[**03**]  Review and export")
        with st.expander("How the shortlist works"):
            st.write("Cuts run for 20–60 seconds. The tool scores the opening hook, unresolved ending, "
                     "clarity, and emotion, then reduces overlap between selections.")
            st.caption("Scores guide editorial review. Check pacing and context against the footage.")
        st.link_button("View the source code", "https://github.com/mukeshbanoth/kukufm",
                       icon=":material/code:")
        st.caption("Built for the Kuku AI Generalist assignment.")

    st.markdown(":violet-badge[PROMO FINDER] :blue-badge[EDITOR WORKSPACE]")
    st.title("Every story has a :violet[standout moment].")
    st.write("Turn timestamped episodes into ranked cuts, with the hook, ending, and exact edit points.")
    if public:
        st.caption("Offline scoring · No API key needed · Original synthetic sample included")

    with st.container(horizontal=True):
        st.badge("20–60 second cuts", icon=":material/timer:", color="violet")
        st.badge("Source-backed quotes", icon=":material/format_quote:", color="blue")
        st.badge("Editor-ready exports", icon=":material/download:", color="green")

    inputs, workspace = st.columns([1, 2], gap="large")
    with inputs:
        with st.container(border=True):
            st.subheader(":violet[:material/upload_file:] Start a new run")
            st.caption("Upload a ZIP of episode-NNN*.txt screenplays.")
            with st.form("run", border=False):
                upload = st.file_uploader("Screenplay ZIP", type=["zip"],
                                          max_upload_size=1 if public else 50,
                                          help="Public limit is 1 MB unpacked and 100 ZIP entries." if public
                                          else "Upload the archive containing your episode text files.")
                path = "" if public else st.text_input("Or use a local folder or ZIP path")
                top = st.number_input("Promos to shortlist", min_value=1, max_value=50, value=15,
                                      help="The tool may return fewer cuts when overlap limits apply.")
                provider = "offline" if public else st.selectbox("Provider", ["offline", "gemini", "openai"])
                model = "" if public else st.text_input("Model override")
                submitted = st.form_submit_button("Generate shortlist", type="primary",
                                                 icon=":material/auto_awesome:", width="stretch")
            st.caption("Just exploring? Run an original one-episode example.")
            sample = st.button("Try the synthetic sample", icon=":material/play_arrow:", width="stretch")
            if public:
                st.caption("Upload scripts you have permission to share. Files are processed in temporary "
                           "storage. Results stay in this browser session until it ends.")

    with workspace:
        if submitted or sample:
            st.session_state.pop("promo_results", None)
            if not sample and not upload and not path.strip():
                st.warning("Add a screenplay ZIP, or try the sample to see a complete result.")
            else:
                try:
                    with TemporaryDirectory() as directory, st.status(
                            "Building your shortlist", expanded=True) as status:
                        temp = Path(directory)
                        st.write("Reading episodes and checking cut boundaries…")
                        source = Path(path.strip().strip('"')).expanduser()
                        if sample:
                            source = ROOT / "demo"
                        elif upload:
                            if public:
                                with zipfile.ZipFile(upload) as archive:
                                    entries = archive.infolist()
                                    if len(entries) > 100 or sum(e.file_size for e in entries) > 1_000_000:
                                        raise ValueError("The public demo accepts up to 100 ZIP entries and 1 MB unpacked.")
                            source = temp / "upload.zip"
                            source.write_bytes(upload.getbuffer())
                        out = temp / "outputs"
                        results = run(source, out, provider, model.strip() or None, int(top))
                        exports = []
                        for report in sorted(out.rglob("promos.json")):
                            files = {p.name: p.read_bytes() for p in report.parent.iterdir() if p.is_file()}
                            bundle = BytesIO()
                            with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
                                for name, content in files.items():
                                    archive.writestr(name, content)
                            exports.append((files, bundle.getvalue()))
                        st.session_state["promo_results"] = (results, exports, sample)
                        status.update(label="Shortlist ready", state="complete", expanded=False)
                except (OSError, ValueError, zipfile.BadZipFile) as error:
                    st.error(str(error), icon=":material/error:")

        if "promo_results" not in st.session_state:
            with st.container(border=True):
                st.subheader(":violet[:material/video_library:] Your next cut starts here")
                st.write("Generate a shortlist to compare the strongest openings and unresolved endings.")
                a, b, c = st.columns(3)
                for column, color, icon, title, description in [
                    (a, "violet", "bolt", "Hook", "An opening that earns attention."),
                    (b, "blue", "visibility", "Clarity", "A conflict a new viewer can follow."),
                    (c, "green", "pending", "Cliffhanger", "A reason to watch what happens next."),
                ]:
                    with column:
                        st.markdown(f"### :{color}[:material/{icon}:]")
                        st.markdown(f"**:{color}[{title}]**")
                        st.caption(description)
                st.caption("Try the sample for a complete result. Upload your episodes when you are ready.")
            return

        results, exports, is_sample = st.session_state["promo_results"]
        show = st.selectbox("Show", list(results))
        rows, stats = results[show]
        files, bundle = exports[list(results).index(show)]
        if is_sample:
            st.badge("Synthetic sample", color="blue")
        metrics = st.columns(4)
        for column, label, value in zip(metrics, ["Episodes", "Candidates", "Selected cuts", "Run time"],
                                        [stats["episodes"], f"{stats['candidates']:,}", len(rows),
                                         f"{stats['runtime_seconds']:.1f}s"]):
            column.metric(label, value)
        st.caption(stats["provider_status"])
        if stats.get("provider_errors"):
            st.warning("Model calls stopped. Remaining candidates use heuristic scores.")

        ranked, exports_tab = st.tabs([":material/format_list_numbered: Ranked shortlist", ":material/download: Export results"])
        with ranked:
            st.subheader(":violet[:material/auto_awesome:] Your strongest cuts")
            st.caption("Review the top five first. Scores are out of 10 and require an editor’s judgment.")
            if not rows:
                st.info("No eligible 20–60 second cuts were found in this input.")
            for row in rows:
                with st.expander(
                    f"#{row['rank']:02}  ·  {row['hook']['type'].capitalize()}  ·  "
                    f"{row['total_duration']:.1f}s  ·  Score {row['base_score']:.2f}",
                    expanded=row["rank"] == 1,
                ):
                    st.caption(segments_text(row))
                    opening, ending = st.columns(2, gap="medium")
                    with opening:
                        st.markdown("**:violet[:material/bolt: Opening hook]**")
                        st.caption(f"Episode {row['hook']['episode']} · {row['hook']['start']}–{row['hook']['end']}")
                        st.write(row["hook"]["quote"])
                    with ending:
                        st.markdown("**:blue[:material/pending: Cliffhanger evidence]**")
                        st.caption(f"Episode {row['cliffhanger']['episode']} · "
                                   f"{row['cliffhanger']['start']}–{row['cliffhanger']['end']}")
                        st.write(row["cliffhanger"]["quote"])
                    st.write(row["why"])
                    st.caption(f"Standalone review · {row['standalone']['reason']}")
                    with st.container(horizontal=True):
                        st.badge(row["hook"]["type"].capitalize(), color="violet")
                        st.badge(f"{row['total_duration']:.1f} seconds", color="blue")
                        st.badge(f"{row['confidence'].capitalize()} confidence", color="orange")
                    st.caption(f"{row['scoring_source']} · {row['kind']}")
                    score_columns = st.columns(3)
                    for column, criterion in zip(score_columns, ["hook", "cliffhanger", "standalone"]):
                        column.progress(row["scores"][criterion] / 10,
                                        text=f"{criterion.capitalize()}  {row['scores'][criterion]:.1f}/10")
                    st.caption(row["rank_reason"])

        with exports_tab:
            st.subheader(":green[:material/download:] Take the shortlist to your editor")
            st.write("Get the cut list, source evidence, run log, and blank review sheet.")
            st.download_button("Download all results", bundle, file_name="promo-shortlist.zip",
                               mime="application/zip", type="primary", icon=":material/folder_zip:")
            for label, name, mime in [
                ("Ranked report", "promos_ranked.md", "text/markdown"),
                ("Editor spreadsheet", "promos.csv", "text/csv"),
                ("Full JSON", "promos.json", "application/json"),
                ("Human review sheet", "review.csv", "text/csv"),
            ]:
                st.download_button(label, files[name], file_name=name, mime=mime, key=f"download-{name}")

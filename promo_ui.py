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
    st.set_page_config(page_title="Kuku · Promo finder", page_icon=str(ROOT / "assets" / "kuku-icon.png"), layout="wide",
                       initial_sidebar_state="collapsed")
    if not public:
        load_dotenv()

    st.logo(str(ROOT / "assets" / "kuku-logo.svg"), size="large", link="https://kuku.app/")
    with st.sidebar:
        st.caption("PROMO FINDER")
        st.badge("Public demo" if public else "Editor workspace", icon=":material/movie:", color="red")
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

    with st.container(horizontal=True, vertical_alignment="center"):
        st.image(str(ROOT / "assets" / "kuku-logo.svg"), width=150)
        st.badge("ASSIGNMENT PROTOTYPE", color="gray")
    st.caption("PROMO FINDER / EDITOR WORKSPACE")
    st.title("Find your next :red[promo].")
    st.write("A screenplay in. A ranked cut list out. Review every hook, ending, and edit point in one workspace.")
    if public:
        st.caption("Offline scoring · No API key needed · Original synthetic sample included")

    with st.container(horizontal=True):
        st.badge("20–60 second cuts", icon=":material/timer:", color="red")
        st.badge("Source-backed quotes", icon=":material/format_quote:", color="blue")
        st.badge("Editor-ready exports", icon=":material/download:", color="green")

    has_results = "promo_results" in st.session_state
    if st.session_state.pop("focus_next_run", False):
        st.session_state["focus_results"] = True
    st.session_state.setdefault("focus_results", True)
    focus = st.toggle("Focus on shortlist", key="focus_results",
                      help="Use the full workspace for results. Turn off to upload another screenplay.") if has_results else False
    upload, path, model, provider, top = None, "", "", "offline", 15
    submitted, sample = False, False
    if not focus:
        with st.container(border=True):
            st.subheader(":red[:material/upload_file:] Drop your screenplay ZIP here")
            st.caption("Drag a ZIP onto the upload area below, or choose Browse files.")
            upload = st.file_uploader("Screenplay ZIP", type=["zip"],
                                      max_upload_size=1 if public else 50,
                                      help="Public limit is 1 MB unpacked and 100 ZIP entries." if public
                                      else "Upload the archive containing your episode text files.",
                                      key="screenplay_upload")
            if upload:
                st.success(f"{upload.name} is ready · {upload.size / 1024:.1f} KB", icon=":material/check_circle:")
            with st.expander("Shortlist settings", expanded=not public):
                top = st.number_input("Promos to shortlist", min_value=1, max_value=50, value=15,
                                      help="The tool may return fewer cuts when overlap limits apply.")
                if not public:
                    path = st.text_input("Or use a local folder or ZIP path")
                    provider = st.selectbox("Provider", ["offline", "gemini", "openai"])
                    model = st.text_input("Model override")
            with st.container(horizontal=True):
                submitted = st.button("Generate shortlist", type="primary",
                                      icon=":material/auto_awesome:", disabled=not upload and not path.strip())
                sample = st.button("Try the synthetic sample", icon=":material/play_arrow:")
            if public:
                st.caption("Upload scripts you have permission to share. Files are processed in temporary "
                           "storage. Results stay in this browser session until it ends.")

    with st.container():
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
                        st.session_state["focus_next_run"] = True
                        st.rerun()
                except (OSError, ValueError, zipfile.BadZipFile) as error:
                    st.error(str(error), icon=":material/error:")

        if "promo_results" not in st.session_state:
            with st.container(border=True):
                st.subheader(":red[:material/video_library:] Your next cut starts here")
                st.write("Generate a shortlist to compare the strongest openings and unresolved endings.")
                a, b, c = st.columns(3)
                for column, color, icon, title, description in [
                    (a, "red", "bolt", "Hook", "An opening that earns attention."),
                    (b, "blue", "visibility", "Clarity", "A conflict a new viewer can follow."),
                    (c, "green", "pending", "Cliffhanger", "A reason to watch what happens next."),
                ]:
                    with column:
                        st.markdown(f"### :{color}[:material/{icon}:]")
                        st.markdown(f"**:{color}[{title}]**")
                        st.caption(description)
                st.caption("The synthetic example runs in one click. Your shortlist will appear here with "
                           "episode times, source quotes, and downloadable reports.")
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
            column.metric(label, value, border=True)
        st.caption(stats["provider_status"])
        if stats.get("provider_errors"):
            st.warning("Model calls stopped. Remaining candidates use heuristic scores.")

        ranked, exports_tab = st.tabs([":material/format_list_numbered: Ranked shortlist", ":material/download: Export results"])
        with ranked:
            st.subheader(":red[:material/auto_awesome:] Your strongest cuts")
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
                        st.markdown("**:red[:material/bolt: Opening hook]**")
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
                        st.badge(row["hook"]["type"].capitalize(), color="red")
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

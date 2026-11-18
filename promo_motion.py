"""Animated screenplay timeline for the landing-page sample preview."""
import streamlit as st

_TIMELINE = st.components.v2.component(
    "promo_timeline",
    html="""
<section class="timeline" aria-label="Illustration of a 29 second promo">
  <div class="toolbar">
    <span class="eyebrow">THE ANATOMY OF A PROMO</span>
    <button type="button" class="motion-toggle" aria-pressed="false" aria-label="Pause timeline animation">
      Pause animation
    </button>
  </div>
  <div class="track" role="img" aria-label="Hook from zero to three seconds, context until twenty-one seconds, cliffhanger until twenty-nine seconds">
    <div class="beat hook"><span>Hook</span></div>
    <div class="beat context"><span>Context</span></div>
    <div class="beat ending"><span>Cliffhanger</span></div>
    <div class="scanner" aria-hidden="true"><span></span></div>
  </div>
  <div class="timestamps" aria-hidden="true"><span>00:00</span><span>00:03</span><span>00:21</span><span>00:29</span></div>
  <p>A strong opening. A clear conflict. An unanswered question.</p>
</section>
""",
    css="""
.timeline {
  color: var(--st-text-color);
  font-family: var(--st-font, sans-serif);
  padding: 12px 0 4px;
}
.toolbar { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; margin-bottom:18px; }
.eyebrow { font-size:11px; letter-spacing:.1em; font-weight:700; }
.motion-toggle {
  min-height:44px; padding:8px 12px; border:1px solid var(--st-border-color);
  border-radius:8px; background:var(--st-background-color); color:var(--st-text-color);
  font:inherit; font-size:12px; cursor:pointer;
}
.motion-toggle:hover { background:var(--st-secondary-background-color); }
.motion-toggle:focus-visible { outline:2px solid var(--st-primary-color); outline-offset:3px; }
.motion-toggle:disabled { cursor:default; opacity:.7; }
.track { position:relative; display:grid; grid-template-columns:1fr 2.3fr 1.8fr; gap:5px; overflow:hidden; border-radius:10px; }
.beat { height:76px; display:flex; align-items:center; justify-content:center; padding:0 5px; font-size:13px; font-weight:650; }
.hook { background:var(--st-primary-color); color:white; }
.context { background:var(--st-secondary-background-color); color:var(--st-text-color); }
.ending { background:var(--st-red-background-color, #fdecee); color:var(--st-red-text-color, #ba1521); }
.scanner { position:absolute; inset:0; pointer-events:none; animation:scrub 9s linear infinite; }
.scanner span { display:block; height:100%; width:2px; background:var(--st-text-color); box-shadow:0 0 8px var(--st-background-color); }
.timestamps { display:flex; justify-content:space-between; margin-top:9px; font:11px var(--st-code-font, monospace); }
p { font-size:12px; line-height:1.5; margin-top:16px; }
@keyframes scrub { from {transform:translateX(0)} to {transform:translateX(99%)} }
.paused .scanner { animation-play-state:paused; }
@media (prefers-reduced-motion:reduce) { .scanner { animation:none; display:none; } }
@media (max-width:380px) { .beat { font-size:11px; } .eyebrow {font-size:10px;} }
""",
    js="""
export default function(component) {
  const root = component.parentElement.querySelector(".timeline");
  const button = root.querySelector(".motion-toggle");
  const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
  let paused = false;
  function sync() {
    root.classList.toggle("paused", paused || preference.matches);
    button.disabled = preference.matches;
    button.setAttribute("aria-pressed", String(paused || preference.matches));
    const label = preference.matches ? "Reduced motion enabled" : paused ? "Play animation" : "Pause animation";
    button.textContent = label;
    button.setAttribute("aria-label", label);
  }
  button.onclick = () => { paused = !paused; sync(); };
  preference.addEventListener("change", sync);
  sync();
  return () => {
    button.onclick = null;
    preference.removeEventListener("change", sync);
  };
}
""",
)


def render_timeline():
    """Display the motion preview with pause and reduced-motion controls."""
    _TIMELINE(key="sample_timeline", height="content", width="stretch")

# Walkthrough script

[Open the terminal in the project folder.]

I picked Find the Promos. A microdrama editor needs a short cut that makes a stranger stop scrolling and want the next scene. I wanted to see how far a tool could get from the screenplay alone. It gives an editor episode numbers and timecodes for the cuts.

I'll run it on the full input pack. This is the offline mode. It works without an API key. The same command works with a new show in the same format. I'm using the ZIP here. A folder of episode files works too.

[Run `python find_promos.py --input "$showZip" --out outputs --provider offline --top 15`. Set `$showZip` to the full archive path before recording.]

The parser reads dialogue, action, camera notes and sound effects. Those tracks can overlap. The tool looks for real event boundaries and checks that they don't land in the middle of a spoken line. It keeps cuts between twenty and sixty seconds. Then it scores the opening, the ending and how easy the cut might be to follow. It limits overlap so the editor doesn't see the same scene five times.

[Open the ranked report after the run finishes.]

Here is one I would show an editor. Episode thirty-four, from one minute thirty-four point two to two minutes six point four. A witness says his wife took Juliana's mixture. We hear what happened to her, and the room turns it into an accusation. When the judge asks whether Juliana gave them the medicine, the cut ends before she answers. I can understand the charge from the clip itself.

[Scroll to Episode 27.]

Here is a weaker pick. Episode twenty-seven opens with someone asking for a husband's name. The tool sees a marriage word and calls that a reveal. The actual tension comes later when people burst into the room and challenge the maid about the medicine. The start time is real, but the opening is slow for an ad.

[Show the validation command and the review CSV.]

The validator checks the timecodes, duration, evidence and overlap. That catches broken cuts and quotes that don't match the script. The review sheet is where an editor can mark whether the hook, cliffhanger and standalone story work.

There's also a model mode. It sends a shortlist to a judge and runs a separate check with just the clip text. I tested that flow with a stand-in provider. I didn't have a Gemini key for this run. Even with a model, I would watch the final few cuts against footage. The screenplay gives me line times. It doesn't tell me exactly when the strongest word lands or how a shot feels on screen.

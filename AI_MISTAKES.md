# AI mistakes found during the build

These came from Codex-written logic in real local runs. They are separate from live model output.

| What happened | How it was found | What changed |
| --- | --- | --- |
| The first scorer tagged Episode 38 at 00:17.50 as a threat because it saw the word “die.” | Reading 00:17.50–00:47.50 showed a guard giving a starving prisoner bread. The line is about compassion. | Penalized dependent openings and excluded this kind of negated threat from the keyword hit. The cut dropped out of the final 15. |
| The first Episode 45 cut ran 00:54.00–01:23.00 and scored “Juliana?!” as a cliffhanger. | The preceding public declaration at 01:14.80 gives away Juliana's status. The final line mostly reacts to it. | Penalized short reactions after a triumphant beat. The selected cut now ends at 01:14.00 before the public declaration. |
| An intermediate run started Episode 28 at 00:10.20 on “…a secret medicine in her hand.” | The screenplay showed that the opening was the second half of an accusation. An event boundary can still be a bad sentence boundary. | Skipped windows that start on a marked dialogue continuation within the first second. |
| The initial quote matcher compared fuzzy text before checking timestamps. | The first full run was slow even though each evidence item named one exact span. | Checked the time span first and reused opening and ending scores across overlapping windows. |

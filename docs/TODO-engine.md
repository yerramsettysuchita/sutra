# Engine defects found while building the UI

Appended during UI sessions, when engine code is read only. Nothing here is
fixed. Each line is what was observed and where.

- Layer 6 collective iteration does not reach a fixed point. `eval.json`
  reports `converged: false` across 8 iterations, F1 oscillating between
  0.5111 and 0.5140 with 166 to 221 rows reassigned each pass. The evaluation
  screen labels it non convergent because that is what the file says.
- Two of six signals have a positive ablation delta, meaning F1 improves when
  they are removed. Relational +0.0316 and phonetic +0.0083, from
  `eval.json.ablation`. Consistent with the correlated signal problem recorded
  in ADR 017, appearing again between the relational and spatial channels.
- Only one cannot link conflict surfaces in the top 300 review band pairs.
  Direct same case pairs are excluded from the candidate set, so conflicts can
  only be transitive, and at the current cluster sizes they are very rare. The
  review queue is built to show them prominently but has almost nothing to
  show.
- `resolution_report.json` persists aggregates only, not per pair evidence, so
  `scripts/export_web.py` has to recompute the whole scoring path to recover
  the review band. That is about ninety seconds of the export. Persisting the
  scored candidate set would remove it.

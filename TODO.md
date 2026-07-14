# TODO

- [x] **Accessibility pass over the generated site.** Done 2026-07-14; findings
      in `docs/a11y-audit-2026-07.md`, reusable harness in
      `scratch/axe_scan.sh` (agent-browser + axe-core, replaces the mortolista
      playwright script). Remediation is the open follow-up:

- [x] **A11y remediation.** Done 2026-07-14; every audit finding cleared
      (axe re-scan zero violations across index/LS/GeS/QVH, light + dark,
      drawer/settings open — see the remediation appendix in
      `docs/a11y-audit-2026-07.md`). Contrast boundary maths live in
      `scratch/contrast_solve.py`. Residual (from the audit's "not covered"):

- [ ] **A11y follow-ups.** Real VoiceOver smoke test; touch-target sizing;
      EPUB/PDF accessibility; drawer tablist arrow-key navigation (tabs are
      `role="tab"` but only Tab-reachable). (`axe.min.js` is now vendored
      at `scratch/axe.min.js`; the `../mortolista` borrow is gone.)

# TODO

- [x] **Accessibility pass over the generated site.** Done 2026-07-14; findings
      in `docs/a11y-audit-2026-07.md`, reusable harness in
      `scratch/axe_scan.sh` (agent-browser + axe-core, replaces the mortolista
      playwright script). Remediation is the open follow-up:

- [ ] **A11y remediation.** From the audit, roughly in severity order:
      contrast lifts (`.para-num` 2.2:1, `.chapter-num` light 3.36:1, dark
      drawer 3.99:1, index sort controls); `<main>` landmark; coherent heading
      outline (title is a `div`, body opens at `h5`, only `h1`s are the
      appendices); drawer keyboard flow (Escape close, focus into panel — its
      first focusable is tab stop 188/299); footnote refs should move focus;
      settings buttons need names ("A"×3) and `aria-pressed`; scroll indicator
      is mouse-only (`aria-hidden` it or make it operable).

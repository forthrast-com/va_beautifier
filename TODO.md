# TODO

- [ ] **Accessibility pass over the generated site.** Run axe-core against the
      built pages (light and dark if applicable) plus a manual keyboard-flow
      check. The sibling mortolista project has a reusable harness at
      `../mortolista/scratch/a11y_audit.js` (playwright-core + axe-core against
      a local http.server); its findings there were the usual suspects —
      unlabelled image links, colour-only link affordances, sub-4.5:1 muted
      text, missing `<main>` landmark, heading-order skips, no live region on
      status text.

# web

Vite, React, TypeScript. One screen, the corpus audit.

```
npm install
npm run dev        # http://0.0.0.0:5173
npm run check      # typecheck, then smoke render against the real corpus
```

## What is here

`src/styles/tokens.css` is the design system. The palette and type stack are
fixed by [CLAUDE.md](../CLAUDE.md) and this file is the only place they are
written down. Measured contrast ratios are recorded in the file header, and all
six text colours exceed 4.5 to 1 against the panel surface.

`src/components/primitives.tsx` is the component vocabulary. Six pieces, Panel,
Rule, Metric, DataTable, StatusPill, AuditStrip. Every screen is built from
these so the visual language is settled once. Two rules are enforced in code
rather than left to discipline. `Metric` and numeric table cells apply
JetBrains Mono with tabular figures, so a number cannot reach the page in the
interface face by accident. `StatusPill` requires a word, and that word is what
assistive technology reads, so status never travels as colour alone.

`src/screens/CorpusAudit.tsx` is the screen.

## It reads the real corpus, in development and in production

The screen fetches `/corpus/manifest.json`, `/corpus/corpus_stats.json` and
`/corpus/blocking_report.json`. One path, one code path, both environments.

`scripts/sync-corpus.mjs` copies those three files from `../data/corpus` into
`public/corpus`, and Vite copies `public/` verbatim into `dist/`. It runs as
`predev` and `prebuild`, and again on change while the dev server is up.

This replaced an earlier arrangement where a Vite middleware served the files
straight out of `data/corpus`. That worked on localhost and would have shipped
a blank page, because dev middleware does not exist in a static build. The
symptom would have appeared only on the deployed URL, which is the worst shape
a bug can take.

Only the three report files are copied. The corpus CSVs and the ground truth
directory never enter the bundle.

The Layer 2 report is optional at runtime. An evaluator may run `make gen` and
`make stats` without `make block`, so the screen degrades to the pre blocking
ceiling and says so. Both paths are covered by the smoke render. It is not
optional at build time, where a missing report fails the build.

## Building for Catalyst

```
npm run build      # prebuild syncs, tsc and vite build, postbuild verifies
npm run serve:static
```

`scripts/verify-dist.mjs` runs automatically after every build and rejects the
bundle on any of:

- a missing or unparseable corpus report, which would render an empty page
- a reference to an asset CDN, `fonts.googleapis.com` and seven others
- any construct that issues a cross origin request at load, stylesheet links,
  script tags, `@import`, `url()`, `preconnect`
- fewer than eight vendored woff2 files

It distinguishes a request from a string. Catalyst's CSP blocks fetches, not
text, so React's embedded `https://reactjs.org` error URL and the SVG namespace
are reported and not failed.

Both failure paths are exercised by hand rather than assumed. Removing a report
and injecting a Google Fonts link each produce exit 1.

`scripts/serve-static.mjs` is a deliberately stupid file server with no
bundler, no middleware and no SPA rewrite, sending a CSP close to what Catalyst
enforces. If the page works there it works deployed.

## Testing

`npm run typecheck` runs with `strict` and `noUncheckedIndexedAccess`, so every
read from the generator's open record types must be defaulted.

`npm run contrast` parses the real token file and fails below 4.5 to 1 on any
text pair.

`npm run smoke` renders the screen to a string against the real JSON, with and
without the Layer 2 report, and fails if the output contains `NaN` or
`undefined` or looks empty.

`npm run check` runs all three. None of them can see layout, colour in practice
or fonts. Those need a browser.

## Generated directories

`public/corpus` and `dist` are both build output and neither belongs in version
control. `public/fonts` is vendored and does belong in it.

## Known gaps

No routing, no 3D, no graph. One screen, deliberately.

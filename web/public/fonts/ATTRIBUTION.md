# Vendored typefaces

Served from our own origin. The Catalyst deployment runs under a strict CSP
with no external hosts, so a Google Fonts link tag works in development and
fails on deploy.

Regenerate with `python scripts/vendor_fonts.py`. The generated
`web/src/styles/fonts.css` is the only thing that references these files.

| Family | Role | Copyright | Licence |
|---|---|---|---|
| Bricolage Grotesque | Display | The Bricolage Grotesque Project Authors | OFL 1.1 |
| Inter Tight | Interface | The Inter Project Authors | OFL 1.1 |
| JetBrains Mono | Data, every number | The JetBrains Mono Project Authors | OFL 1.1 |
| Noto Sans Kannada | Kannada | The Noto Project Authors | OFL 1.1 |

All four are licensed under the SIL Open Font License, Version 1.1, which
permits bundling and redistribution with an application. The full licence text
is in `OFL.txt` alongside these files and must ship with any release.

Only the subsets SUTRA renders are kept. Latin and Latin Extended for the three
Latin faces, Kannada and Latin for Noto Sans Kannada. Cyrillic, Greek and
Vietnamese are dropped, which is most of the original payload.

Eight files, 394 KB total. All are variable weight, so one file covers the whole
weight range the design uses.

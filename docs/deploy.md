# Deploying SUTRA to Catalyst

The deployed URL is **https://sutra-gfrnnril.onslate.in/** and it never changes.

**Never create a new Catalyst app.** Always overwrite the existing one. App
`sutra`, deployment `default`. A new app means a new URL, and the URL is quoted
in the README, in the submission and on every screen of the product itself.

---

## What is being deployed

A static bundle. Nothing else.

```
sutra.zip
├── index.html              at the archive root, not inside a folder
├── assets/                 the built JavaScript and CSS
├── fonts/                  four families as local woff2
├── corpus/                 three corpus reports
└── data/                   the JSON feeds the client reads
```

There is no server, no function, no database and no runtime dependency.
Resolution is a nightly batch job that runs locally, writes JSON, and Catalyst
serves it. That is ADR 002, and it is why five of the six Catalyst services show
as not used on the `/status` screen.

Two consequences worth knowing before you deploy.

The site is **fully static**, so it will work behind any host, and the deployed
figures are only as fresh as the last `make all`. The provenance bar under the
masthead carries the corpus timestamp on every screen, so a reader can always
see how old the answer is.

Catalyst applies a **strict content security policy** that blocks external
hosts. Every font is vendored locally for that reason. `npm run build` runs
`verify-dist.mjs` afterwards, which greps the bundle and refuses to package
anything that would issue a cross origin request.

---

## Building the bundle

From the repository root.

```
make all                       regenerate every figure from seed 4471
npm --prefix web run build     build and verify the static bundle
python scripts/package_catalyst.py
```

The last command writes `catalyst/sutra.zip` and prints the path. It refuses to
package if `index.html` is not at the archive root, if a corpus report is
missing, or if `verify-dist` rejected the bundle.

If you only changed the interface and the engine output is current, the first
command is unnecessary and the second two take about forty seconds.

---

## Deploying, console route

This is the route this project has always used. It needs no CLI and no install.

1. Open the Catalyst console and select the existing **`sutra`** app.
   Do not create a new one.
2. Go to **Web Client Hosting**.
3. Choose to upload a new version and select `catalyst/sutra.zip`.
4. **Upload the contents of the archive, not a folder containing them.**
   `index.html` has to land at the web root. If the console shows a single
   folder after upload, the zip was made wrongly and `package_catalyst.py`
   should have caught it, so re-run the packager rather than reorganising by
   hand.
5. Deploy to the **`default`** deployment.

Then check the URL. The masthead should read Karnataka State Police above the
SUTRA wordmark, and the provenance bar under it should carry the seed and the
corpus timestamp from the run you just built.

---

## Deploying, CLI route

Catalyst has a command line tool, installed through npm, that can push a
directory without going through the console. If you use it, point it at
`web/dist` rather than at the zip, and keep the app and deployment names
unchanged.

**Check the current Catalyst CLI documentation for the exact commands.** The
tool has changed its authentication flow more than once, and a stale command
copied out of a repository is worse than no command, because it fails in a way
that looks like a broken build rather than a broken instruction.

The console route above is the one this project has verified.

---

## Deploying from GitHub

**Catalyst Web Client Hosting has no native GitHub integration.** There is no
equivalent of connecting a repository and having a push deploy itself, so a
push to `main` will not update the live site on its own.

To automate it you would need a GitHub Actions workflow that checks out the
repository, installs Node and Python, runs the build, and then calls the
Catalyst CLI with credentials held as repository secrets. That is a real option
and it is not currently set up here.

Two things to weigh before doing it.

The build needs Python with numpy, scipy, scikit-learn and networkx if the
workflow regenerates the corpus, which takes several minutes of runner time. A
lighter workflow would commit the exported JSON, which this repository already
does, and build only the client.

Storing Catalyst credentials in GitHub secrets puts deployment authority in a
second place. For a submission with one maintainer and an occasional deploy, the
console route is less machinery for the same result.

---

## Verifying a deployment

Open the URL and check these five things. They take a minute and they catch
every failure this bundle has ever had.

1. **The masthead renders in navy** with the Karnataka State Police attribution
   above the wordmark. If the page is unstyled, the CSS did not upload.
2. **The provenance bar** under it shows a seed and a corpus timestamp. If it
   says `not exported`, the `data/` directory is missing from the archive.
3. **The fonts are right.** The wordmark is Bricolage Grotesque and every number
   is monospaced. If both look like the system sans, the CSP blocked something
   or `fonts/` did not upload.
4. **Switch to ಕನ್ನಡ** in the masthead. The navigation should change and every
   number should stay exactly as it was.
5. **Open `/status`.** It should list every claim with its true state. That
   screen is the honest inventory of the project and it is the one a jury is
   most likely to read closely.

If the first four pass and the site is blank on one route only, open the browser
console. A blank route with no error is usually a missing JSON feed, and the
screen itself will normally say which command produces it.

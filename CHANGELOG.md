# Changelog

All notable changes to Imprint, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## How versions are numbered

Imprint's version is `v<MAJOR>.<BUILD>` (for example `v2.248`), shown in the
header bar. `MAJOR` is the single integer in the `VERSION` file (currently 2).
`BUILD` is the number of commits on the branch (`git rev-list --count HEAD`),
so it goes up by one with every commit and is never typed by hand. See
README section 18.1.

There are no git tags and `VERSION` has changed once (set to 2 on
2026-09-22), so there are no named releases to group by. Entries are grouped
by date, and by month for older work. The build number is not recorded next to
each entry, because commits were rewritten in September (see 2026-09) and a
number written here would drift from `git rev-list --count`. To find the build
a change shipped in, look up its commit.

This file is generated from `git log`; see the note at the bottom for how to
regenerate it. It states what the code does, not how well it works for you:
nothing here is a claim about income, sales or publishing results.

## 2026-10-14

### Added
- Settings -> API keys has a **Qwen workspace ID** field (`DASHSCOPE_WORKSPACE_ID`,
  Singapore only). Entering the ID sends Qwen chat to
  `https://<id>.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`, the host
  Alibaba recommends. The ID must be one plain label (letters, digits, hyphens);
  anything else is ignored with a visible message, so the ID can only point the
  key at a `*.ap-southeast-1.maas.aliyuncs.com` host. `DASHSCOPE_BASE_URL`
  still overrides it; when that URL is the standard host, the Qwen note says to
  clear it rather than to set the ID. Wan video and Qwen Image are not changed.
  An ID that is set but invalid is also named, without its value, in the Qwen
  hover note and `scripts/check_keys.py`.
- When a Qwen key check on a workspace host returns 401, the note says the key
  may belong to a different workspace or region.
- The Qwen **Test** result names the host that answered: "via workspace host",
  "via standard host" (plus "(workspace ID ignored)" when a typed ID did not
  apply), or the host name of a typed endpoint, such as "via dashscope.aliyuncs.com".
- A hand-typed `DASHSCOPE_BASE_URL` or `DASHSCOPE_VIDEO_BASE_URL` that is not
  https (plain http to localhost is fine) or not on `aliyuncs.com` is still used,
  but its Settings row, the Qwen hover note and `scripts/check_keys.py` warn that
  the key is sent there.

### Fixed
- A blank `DASHSCOPE_BASE_URL=` or `DASHSCOPE_VIDEO_BASE_URL=` (as shipped in
  `.env.example`) is now treated as unset and falls back to the default host.
  Before, the empty string was used as the base URL, so every Qwen call (or Wan
  video or Qwen Image call) from a `.env` with the blank line failed. It failed
  before sending anything: the URL had no host, so the key went nowhere
  (checked against openai 2.31.0 and requests).

### Security
- Settings -> API keys refuses a value with a line break, such as a two-line
  paste, and names the field ("must be one line only"); nothing on the page is
  written. Before, pasting `ws1`, a new line and `DASHSCOPE_BASE_URL=…` into one
  box could leave a second line in `.env` that Settings read back as
  `DASHSCOPE_BASE_URL`; one more Save made it a setting the app loads at launch.

### Changed
- The Qwen endpoint note no longer says the international host is in
  "maintenance mode since 2026-09-30", which no primary source confirmed. It now
  says a workspace host is recommended and the standard host still works.

## 2026-10-12

### Security
- A new `.env` file is now created readable by its owner only (permissions
  0600), including when it is seeded from the template on first launch.
- If moving the old "Create & Publish" data folder to the new Imprint folder
  fails, the app now keeps using the old folder for that run and tries again
  next launch. Before, a failed move could leave a blank new folder behind
  that hid your keys and database on every later launch.
- The folder move is now a single atomic step, and a test checks that a legacy
  database keeps writes that were still in its write-ahead log.

### Added
- Two GitHub Actions workflows: `quality.yml` (tests with coverage, and a
  lint count that may not rise) and `security.yml` (gitleaks secret scan and a
  pip-audit of `requirements.txt`). Also a gitleaks config, `ruff.toml`, a
  Dependabot config and a pre-commit hook file. The hook is not switched on
  by default; run `git config core.hooksPath .githooks` to use it.
- Company process files: role playbooks, `AGENTS.md`, and a tooling baseline
  (`docs/company/tooling/baseline.json`) that the ratchet script checks so
  lint counts cannot rise.

### Changed
- The test that checks for retired names now also scans files that are not yet
  committed (new but not ignored), so a retired name cannot slip in before its
  first commit.
- Press: the Overview sidebar no longer adds a second scrollbar; the
  to-do list is a checklist that gives way before the panel scrolls.

## 2026-10-11

### Added
- Settings -> API keys: paste a key, press Test, then Save All. The window
  rebuilds its provider clients, so there is no file editing and no restart.
  `services/api_keys.py` is the single list of credentials the code reads.

### Fixed
- The model-ratings fetch remembers a failed try, so an offline Mac waits a
  day instead of fetching again at every launch.

## 2026-10-09

### Added
- `tests/TEST_PLAN.md` and `tests/READINESS_GATE.md`: the test plan and the
  check of each agent's promise against its code before QA starts.
- `scripts/check_setup.py`: checks Python 3.11+, the data folder, ffmpeg and
  ffprobe (required), and Calibre, `say` and Ollama (optional).

### Changed
- Six catalog lines now say only what ships (for example Herald: publish to
  Reddit, YouTube and Pinterest; Label: audio is made in Suno).
- Docs in four places now say Booth narrates by three routes, not OpenAI only.

### Fixed
- `PUBLISHDRIVE_API_KEY` was read by the code but missing from `.env.example`
  and `scripts/check_keys.py`; a test now requires every secret the code reads
  to be in the template.
- The on-device voice fallback used to write a silent MP3 and call it success;
  it now fails with an error.
- `scripts/check_keys.py` imported classes that do not exist; fixed.
- Stamp orders close and keep their edits; the Glimmer pull drives Chat's
  progress bar.
- Tooltips: setting them to Off no longer hid a clipped field's full value in
  every window after the first.

## 2026-10-08

### Added
- Text model "best fit" now uses LMArena ratings (credited, CC BY 4.0): the
  cheapest model rated within 20 points of the best wins.
- Muse Glimmer shows download progress.

### Changed
- Every panel is lined up on one grid.
- Booth keeps its own conversion log instead of writing into Chat's.

## 2026-10-07

### Added
- Every paid request is assessed for which provider and model fits it best,
  including image, video and speech requests. A model is not switched for
  being new. The Model updates tile in the rail applies marked updates only
  where the marked model wins the assessment.
- Narration routes in Booth: OpenAI, Gemini or ElevenLabs, chosen per book.
- Images from Gemini and Qwen as well as the existing providers; Muse teasers
  from Higgsfield, Gemini Omni or Wan 3.0.
- Learning Centre pages for paid-request assessment and Model updates.

### Changed
- Model lists and prices brought current; every offered model has a price row.
- The live launcher is a small C program, so the app is named Imprint (not
  "python") in Activity Monitor and the Dock, and no longer shows as Not
  Responding.
- Quill, Manuscript and Booth's Listen tab scroll instead of squeezing rows;
  spin boxes and date edits keep their own widths.

### Fixed
- Veo is removed on its shutdown date; ElevenLabs and Higgsfield requests
  match what their APIs read; a paid Gemini render is never posted twice.
- Ranking: no unpriced winner, and ties do not move the badge.

## 2026-10-06

### Added
- Three themes, picked from three dots.
- A menu bar item with Open and Quit. Closing the window still quits the app.

### Changed
- Narrator tools run in the launch environment; one conversion per book folder
  at a time.
- `.env` is created from the template with every secret blank; README section
  19 now lists every provider key and what it unlocks.
- Docs for Imprint and six agents brought back in line with the code.

### Fixed
- A test-suite hang: the media engine no longer outlives its widget.
- Muse's teaser resume never worked on an existing database (a duplicated key
  left four columns unadded).
- Narrator: a chunk stopped mid-stream is no longer marked done; a chunk cut
  short by a stop is redone.
- The free-local-model offer now names a model that is actually pulled.

## 2026-10-05

### Added
- Local-model offer: when a budget cap refuses a request, the app asks whether
  to switch the agent to Ollama. The request is not re-sent for you.
- Music plans are saved records; Client Gigs keeps one durable order per
  client with a reusable brand kit; Site Builder exports in a project shape
  with checks you rule on.
- Booth offers AZW3 where the converter accepts it; Publishing Manager shows
  each integration's last sync outcome; Social explains what connecting grants.
- `ui/charts`: a bar chart, first used for KDP royalties.
- Learning Centre: every agent lesson has a Show me recipe.
- UAT scenarios for the ten agents that exist (`tests/manual_test_cases.md`).

### Changed
- Money readouts and source/scope handling hardened across the second feature
  wave (thirteen confirmed defects fixed in one pass).

## 2026-09-30

### Added
- Audiobooks: save to this Mac or a synced Google Drive folder; progress
  follows the same choice. M4B with chapters; EPUBs read in spine order.
  `cloud/` holds a web agent that is not deployed.
- Router can reach an agent by its own name and says how sure it is.

### Changed
- Agents renamed to codenames (Quill, Press, Booth, Label, Reel, Herald,
  Sitebuilder, Stamp, Muse, Chat); each workspace shows a one-line description.
  Catalog keys, settings and the database are unchanged.
- vidforge is part of this repository rather than a separate nested one.
- Audiobook Studio merged into Imprint.

### Removed
- Muse's platform-specific features, which Backstage owns.
- The Primer course generator (never shipped) and `creator_earnings`.
- vidforge's standalone GUI and its `schedule` command, which could start
  paid renders outside the request guard. `python -m vidforge.cli` still runs.

## 2026-09 (summary)

Mostly Sept 7-29; the repository history was rewritten on 2026-09-24 and
2026-09-27 (the commits say so), so build numbers from before then no longer
match.

### Added
- The app was renamed Imprint (2026-09-08). On launch it moves the old data
  folder and database forward, with their write-ahead files, without
  overwriting newer data.
- GUI rebuilt: one header bar and two fixed rails, a shared form system,
  rebuilt panels for each agent, a Learning Centre with guide pages and
  screenshots, and "Show me" recipes.
- Agents: Creator (planning, persona, calendar week view), Video (vidforge as
  an agent), Social (posting where an API exists), an audiobook library with a
  resuming player.
- Projects: shared work identity across agents, a cross-agent overview, and
  immutable approved manuscript versions.
- Durable jobs: video renders, Creator teasers, audiobook conversions and the
  Social publishing queue survive a restart. A publish with an unclear result
  becomes "Verify platform" instead of being retried.
- Header version badge (`v<MAJOR>.<BUILD>`), 2026-09-22.
- Chat streams from every provider, including Ollama.

### Changed
- Pricing: prompt-cache rates, per-unit work (renders, narration) is priced,
  and both budget limits sit on one row.
- Each agent lives in its own package; the host-control aliases are gone.
- Higgsfield defaults to Seedance 2.5 with a 2.0 fallback.

### Fixed
- Money integrity and lifecycle gaps from the 2026-09-20 re-analysis; several
  review rounds of defects in video, teaser, calendar and audiobook
  persistence.

### Removed
- Sora (the Videos API is gone) and the venture dashboard workspace.
- Creator's adult-platform rules and performer records.

### Security
- The secret-scan allowlist is re-pinned after each history rewrite, and one
  deployment note was kept out of the public repository.

## 2026-08

- Forked from `sentinel_ai` (08-18) as Atelier, then Create & Publish; the
  security verticals were stripped from the fork.
- Anthropic pricing corrected; Qwen pricing added. Request-guard and book
  pipeline tests; `ui/` extracted from `main.py`.

## 2026-06 to 2026-07

- Initial commit (06-16); narrator merged in as an in-process module; project
  prepared for GitHub. July holds only automatic sync commits.

## Regenerating this file

Run `git log --reverse --format='%ad %h %s' --date=short`, drop lines that
start with `autosync:` and pure merges, and group by date. Read the commit
body where a subject is unclear. Keep one line per user-visible change.
Cross-check each line against the code. As of the 2026-10-13 build
(248 commits), 21 are autosync commits and 16 are merges.

# Support-readiness audit

Role: `customer-support` (read-only on code and existing docs). Date: 2026-11-23.
Tier: `public` (`docs/foundry/app-context.md:10`), which requires `SUPPORT.md` and a private
security contact.

Commit: briefed at `ec1cda5`. `main` moved to `f69176e` while the audit ran (the rename to
"Imprint Studio" merged). Every file:line below was re-checked at `f69176e`.

Playbook: `docs/playbooks/customer-support.md` front matter says `status: current`,
`last-reviewed: 2026-11-11` (12 days old, inside the 90-day limit). Its body line 17 still reads
"Baseline: seeded from general practice ... not yet verified by a radar run", which contradicts
the front matter. Foundry owns that file; not edited here.

Not run: the app, the test suite, any provider call. Messages are quoted from the code, not from
a screen.

## Verdict

The tier's two requirements are met. `SUPPORT.md` says where to ask, what to put in a report,
what the app is not, and a response target one person can keep ("about once a week", 7 days as a
target, `SUPPORT.md:17`). `SECURITY.md:8-9` points at GitHub's private vulnerability form, which
is switched on for the repo (GitHub API, 2026-11-23: `private-vulnerability-reporting` returns
`enabled: true`), so a private route exists that shows no personal name or email; the tracked
files and every author and committer across all 477 commits (`git log --all`) carry only
`wwds-dev`, bot and noreply identities. No report has gone
unanswered because none has arrived: 0 issues and 0 advisories, ever. Nothing reaches support
yet beyond that tracker; there is no other channel.

It is not ready for strangers on two counts, both P1. First, three open money defects are listed
only inside per-agent reference sheets, `SUPPORT.md` names none of them, and two Learning Centre
lessons tell the user the opposite of what the code does. Second, the bug-report instructions do
not name any diagnostic a user can attach and do not warn that the obvious attachments (the
database, saved chats, the launch log) hold manuscript text, on a tracker where everything
posted is public. No P0.

Refund, withdrawal and complaint wording: not needed and not drafted. The app is free, takes no
payment and has no account (`docs/foundry/app-context.md:17`). A data-request procedure is not
needed either: there is no telemetry, account or server (`docs/legal/privacy.md:11`), so the
owner holds no user data; the only user content the owner can see is what a user posts in a
GitHub issue, which that user can edit or delete there. Both change if the tier is raised to
`commercial`, and `docs/legal/privacy.md:58-59` already lists "a support inbox" as a trigger for
a re-screen.

## Findings

### P0

None.

### P1

**S-1. Known money defects are not in any support-facing list, and two lessons state the
opposite.**

Evidence. `SUPPORT.md:26-30` ("Known limits") lists platform, provider drift and the untested
PublishDrive connector, nothing else. `docs/support/` does not exist. The open rows of
`TODO.md` against what a user can read:

| `TODO.md` row | What happens | Disclosed | Contradicted by |
|---|---|---|---|
| `:96` P0, Reel, QH-2 | Stopping a Gemini Omni render throws the paid clip away: `ui/workers.py:408-409` returns on cancel after the synchronous render, and `services/gemini_client.py:416-419` refuses to resume Omni | `docs/agents/video.md:119` | `docs/learn/modules/24-video.md:208-216` ("Stop without losing the money ... never loses a paid render"), also `:42-46` and `:77-79`; the lesson's own worked example is Omni (`:120`, `:158`) |
| `:61` P0, Booth, QB-2 | After the book's text changed, the whole book is narrated again while only the remaining share was approved | `docs/agents/audiobook.md:55` | `docs/learn/modules/22-audiobooks.md:203-207` ("the approval covers only the missing chapters"), with no exception for a changed book |
| `:62` P0, Herald, QB-3 | A clip approved as OpenAI can spend on Gemini or Qwen with that box unticked | `docs/agents/social.md:58` | none found |
| `:97` P1, Press, QH-5 | Ask claims KDP and store-status access it lacks; Connections says "connected" for an untested key | `docs/agents/manuscript.md:60-61`; partly `SUPPORT.md:30` | none found |
| `:142` P1 | Kimi and Qwen send a `max_tokens` name never run against a live key; the row itself says a rejected parameter fails every request | nowhere | n/a |
| `:116` P1 | Routing advisor never run with a real LM Studio model | nowhere | n/a |

Not user-facing, so not known issues for a user: `:95` (owner-only cloud companion), `:158` and
`:167` (the owner's own `.env`), `:63`-`:66`, `:80`, `:367`, `:390`.

What the user experiences. Follows the Reel lesson, presses Stop on an Omni render believing
the next launch will save it, and has paid for a clip that no longer exists. Or edits a chapter,
resumes Booth, approves a fraction and is billed for the book. Opens `SUPPORT.md` to see whether
this is known: nothing. The four disclosures that exist sit in four different reference sheets
under "Deliberate limitations", which two of them are not.

Smallest fix. (a) One known-issues list, either `docs/support/known-issues.md` or a section in
`SUPPORT.md`, with the first four rows above: what happens, the workaround already written in
each sheet, "open" until the `TODO.md` row closes, then removed. Link it from `SUPPORT.md`.
Support can draft it; it is not drafted here by instruction. (b) `tech-writer` corrects the two
lesson passages (Omni is the exception to the Stop contract; a changed book is the exception to
"only the missing chapters"). (c) Decide whether rows `:142` and `:116` are worth one line each
("not yet run against a live account"), as `SUPPORT.md:30` already does for PublishDrive.

**S-2. The bug-report instructions name no diagnostic to attach and do not warn what the
obvious attachments contain.**

Evidence. `SUPPORT.md:11` asks for the header version, macOS version, steps, expected and
actual, and says not to paste keys, `.env` or manuscripts. It does not mention the provider and
model, the exact message, how the app was started, the Run Log, or any log file. What exists:

- `runs` table: the first 200 characters of every prompt (`services/run_logger.py:24`, fed the
  full prompt at `main.py:4337` and `:4588`) and the raw provider error text (`main.py:5774`).
  `services/api_keys.py:352-353` notes that a provider's error can echo the request.
  `docs/legal/privacy.md:36` lists the table as kept with no expiry.
- `data/chats/` and the database hold whole conversations and drafts.
- `/tmp/imprint_launch.log`: all stdout and stderr of a live-launcher session
  (`scripts/app_launcher.c:123-132`, path set at `scripts/install_app.sh:70`), created `0644`.
- The Run Log window itself shows no prompt text (`ui/dialogs.py:277-291`), only the error
  column; `scripts/check_setup.py` states that it contacts no provider and prints no key
  (its header, line 17).

The two in-app notes on reporting (`docs/learn/modules/17-troubleshooting.md:105-108`,
`docs/agents/overview.md:162-164`) ask for more than `SUPPORT.md` does, say never to include a
key, and say nothing about manuscript text or where to send the report.

What the user experiences. A helpful user attaches the database or the launch log to a public
issue and has published part of an unpublished manuscript, permanently as far as search engines
and forks go. A cautious user attaches nothing, and the owner needs a round trip on a weekly
reading cycle to learn which provider and model were in use.

Smallest fix, in `SUPPORT.md` only: ask for the agent, provider and model, the exact message,
how the app was started (terminal, the installed launcher, a frozen build) and the commit shown
when hovering the version badge; name two safe attachments (the Run Log row's status and error
text, read first for anything private, and the output of `scripts/check_setup.py`); and say
plainly never to attach `imprint.db`, `data/chats/`, `.env` or the launch log unread, because
they hold drafts and prompts. An issue form under `.github/ISSUE_TEMPLATE/` would carry the same
list and warning at the moment of filing (outside support's files; a suggestion).

### P2

**S-3. A crash leaves no evidence a user can send.** No log file is written by the app: no
`logging` setup, no `sys.excepthook`, no `faulthandler` (grep over `main.py`, `services`, `ui`,
`agents`: no match). The only log is the launcher's, which exists only for the installed live
launcher, is opened with `O_TRUNC` on every start (`scripts/app_launcher.c:127`), so reopening
the app erases the trace of the crash, and is absent for a frozen build (`Imprint.spec:125`,
windowed, nothing captures stderr; inferred, not run). `README.md:44` says "logs" live in
`data/`; nothing writes there (`data/logs/` does not exist; `README.md:3021` calls it legacy).
User: the app vanishes, they reopen it, and there is nothing to report but "it crashed".
Smallest fix: keep the previous launch log (rename to `imprint_launch.prev.log` before
truncating) and say in `SUPPORT.md` to copy it before reopening; a proper rotating log under
Application Support is the fuller fix (engineer, a backlog item). Drop "logs" from
`README.md:44` until one exists.

**S-4. On Send, most provider failures are raw SDK text with no next step and no help entry.**
Anthropic alone translates 401, 429, connection and 404 (`services/anthropic_client.py:142-171`).
OpenAI, DeepSeek, Kimi, Gemini and Qwen pass the exception through as
"`<Provider> streaming request failed: <SDK text>`" (`services/openai_client.py:183`,
`deepseek_client.py:130`, `kimi_client.py:127`, `gemini_client.py:474`, `qwen_client.py:417`),
shown as `[Error]` plus that text (`ui/workers.py:125`, `main.py:5766-5774`). The Troubleshooting
lesson covers the Settings **Test** result (`17-troubleshooting.md:21`) but has no entry for a
refused key or a rate limit met on Send; "401", "429" and "rate limit" appear in no lesson
(grep over `docs/learn/modules`). `TODO.md:167` records that Gemini answers a bad key with 400,
not 401, so a user searching for the number finds nothing either way. User: reads a Python dict
in the output box. The provider's own sentence is usually enough for 401; for 429 nothing says
whether money was spent or whether to wait. Smallest fix: two Troubleshooting entries keyed on
"streaming request failed" (key refused: re-paste in Settings, Test, Save All; rate limited:
wait, nothing was billed for a refused request, check the provider's limits page).
Per-provider translation as Anthropic has it is the fuller fix.

**S-5. Anthropic's two key messages send the user to the wrong place.**
`services/anthropic_client.py:111-112` and `:177-178`: "Add it to your .env file and restart the
app."; `:146` and `:191`: "update ANTHROPIC_API_KEY in your .env file". The supported route is
Settings, API keys, Save All, with no restart (`docs/learn/modules/13-access-privacy.md:47-55`),
and a frozen build's `.env` is not where a user would look. Smallest fix: reword both to
"Settings → API keys" (engineer).

**S-6. With Ollama stopped, Send fails with a transport error, not the sentence the lesson is
keyed on.** The friendly text exists only in the model menu and the routing advice
(`services/local_models.py:299`, `main.py:3992`). A request sent anyway ends in
"Ollama streaming request failed: ..." followed by the `requests` connection text
(`services/ollama_client.py:285`). `17-troubleshooting.md:37` is keyed on "Ollama is not
running". No pre-send check was found. Smallest fix: wrap a connection failure in
`ollama_client` as "Ollama is not running. Open Ollama, then press Refresh Models.", which makes
the existing lesson entry match.

**S-7. The version a user is asked for can be meaningless.** `SUPPORT.md:11` asks for "the
version in the header bar". A ZIP download of the public repo has no `.git`, so the badge reads
`v2.???` (`services/version.py:137`); a shallow clone counts only the commits it fetched (how
`git rev-list --count` behaves; not run here). The commit hash is in the badge tooltip
(`services/version.py:185-197`), and the badge is one of two things the header drops when the
window is narrow (`main.py:2489`). Smallest fix: ask for the commit as well (covered by S-2's
wording) and say that `v2.???` means "say how you downloaded it".

**S-8. Error text a user is told to quote may carry a fragment of the key.** Nothing redacts
provider text before it is shown or stored (grep for redact, mask, sanitise: no match;
`main.py:5774`). `services/api_keys.py:376` trims the Test result to 90 characters for this
reason; the Send path does not trim. Whether a given provider echoes part of a refused key was
not observed (see Could not verify). Smallest fix: one sentence in `SUPPORT.md` ("read an error
before pasting it; a provider may repeat part of your key or your text"); the code fix is a
redaction pass over known key shapes before display and storage (security-engineer to judge).

**S-9. Nothing in the app or the README leads to the support channel.** `README.md` never
mentions `SUPPORT.md`, `SECURITY.md` or the issue tracker (grep: no match); its help pointer
(`README.md:48`) ends at the Troubleshooting lesson, whose last entry
(`17-troubleshooting.md:105-108`) says what to put in a bug report and not where to send it.
There is no Help or About entry (grep of `main.py`). GitHub surfaces both files on its own
pages, so a user who starts there finds them; a user inside the app does not. Smallest fix: one
line under "Something not working?" in the README and one at the end of the Troubleshooting
lesson (tech-writer).

**S-10. The reading promise has no mechanism behind it.** "Issues are read about once a week"
(`SUPPORT.md:17`) and "Acknowledgement within 7 days" (`SECURITY.md:16`) rest on the owner
remembering; no recurring item exists in `TODO.md` and whether the account watches the repo was
not checkable. Untested so far: zero reports. Smallest fix: the owner confirms GitHub
notifications for issues and security advisories on this repo, or one recurring `@me` item.

### P3

- **S-11.** `SUPPORT.md:20` and `:24` still say "Imprint" while `:3` says "Imprint Studio" (the
  rename touched only the first line). Support can fix this in its own file.
- **S-12.** `services/validator.py:127` says "Enable it in the API Permissions panel"; no control
  carries that name (the fields are "Cloud text models" and "Paid media", `main.py:2705`,
  `:2721`). The lesson translates it (`17-troubleshooting.md:26-29`).
- **S-13.** Booth's blocked and ready messages say "click Start" (`agents/audiobook/panel.py:292`,
  `:917`, `:921`, `:927`); the button is "Convert audiobook" (`:262`).
- **S-14.** Booth's ffmpeg message says "Install ffmpeg" without the command
  (`services/narrator/converter.py:309-310`); the video pipeline's gives it
  (`vidforge/vidforge/ffmpeg_utils.py:31`). The lesson gives it (`17-troubleshooting.md:66-68`).
- **S-15.** The agent-cap and project-cap refusals say only "Pick a cheaper or local model"
  (`services/validator.py:147`, `:161`), unlike the session and daily ones (`:175`, `:190`). The
  lessons say where each cap is set (`17-troubleshooting.md:55-56`, `14-costs-limits.md:24`).
- **S-16.** `main.py:4445` (docstring) names `/tmp/sentinelai_launch.log`, the pre-fork path.
- **S-17.** `SECURITY.md:29` names `vidforge/` and the narrator as in scope but not `cloud/`,
  which holds an OAuth flow and an encrypted refresh token (`cloud/README.md`). "This repository"
  covers it; naming it would be clearer.
- **S-18.** `docs/foundry/app-context.md:16` says the repo "has no `LICENSE`"; it has one (MIT,
  `LICENSE:1-3`). Already noted for the owner at `TODO.md:77`.
- **S-19.** `SECURITY.md:24` supports "only the latest commit on `main`" while CI on `main` is
  red (`TODO.md:63-64`). Not a broken promise, but the supported version is one that fails its
  own checks.

## What holds

- Missing key: every client says which variable is missing (for example
  `services/openai_client.py:87`); lesson entry at `17-troubleshooting.md:16-19`.
- Budget refusal: "Not sent: this request can cost up to ..." names the cap, what is left and
  the remedy (`services/validator.py:51`, `:175`, `:190`); lesson entry at `:51-57`. This is the
  best-worded message in the set.
- Permission box unticked: message at `services/validator.py:127`; lesson entry at `:26-29`.
- ffmpeg missing: message at `services/narrator/converter.py:309`; lesson entry at `:66-68`.
- Booth quota or key refusal: `[Blocked]` with the provider's reason and the resume step
  (`agents/audiobook/panel.py:910-929`); lesson entry at `:74-77`.
- The eleven lesson strings checked against the code all exist (for example "unreachable — " at
  `ui/dialogs.py:620`, "must be one line only" at `ui/dialogs.py:1015`, "too big now" at
  `services/local_models.py:44`).
- The Learning Centre search is offline and matches error wording
  (`ui/learning_center_v2.py:378`, placeholder "Control, task, or error…"); F1 opens it
  (`main.py:413`).

## Could not verify

- What a live provider returns for a refused key or a rate limit: no provider call was made.
  S-4 and S-8 rest on the code path and on the texts recorded at `TODO.md:167`.
- Whether any provider echoes part of a refused key in its error (S-8).
- What a real session writes to `/tmp/imprint_launch.log`: the file is outside the app root and
  was not opened.
- Frozen-build behaviour (S-3): no frozen build was run.
- The shallow-clone version count (S-7): not run.
- Whether the owner's GitHub account is notified of new issues and advisories (S-10).
- Whether the private report form renders for a signed-out or third-party visitor; the API
  reports the feature enabled, which is all that was checked.
- Every message as it appears on screen: the app was not launched.
- Markets are `UNVERIFIED` in `docs/foundry/app-context.md:19`; nothing here depends on them
  while the app is free.

No agent is a lawyer: the statements above about refunds and data requests describe what the
app's files say it does, not what the law requires.

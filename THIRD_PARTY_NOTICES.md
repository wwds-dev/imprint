# Third-party notices

Imprint Studio's own code is under the MIT licence (`LICENSE`). It runs on
third-party packages that keep their own licences. The list below comes from
each package's metadata (`requirements.txt`, read with `importlib.metadata`);
the full inventory and its limits are in the legal pack (`licences.md`).

## Copyleft dependencies: read these first

| Package | Licence | What it is used for |
|---|---|---|
| **EbookLib** 0.20 | **AGPL-3.0-or-later** | Reading and writing EPUB books (`agents/author/book_exporter.py`, `services/narrator/converter.py`) |
| PySide6, shiboken6 (Qt 6.11) | LGPL-3.0-only, GPL-2.0-only or GPL-3.0-only | The desktop interface |
| certifi | MPL-2.0 | Certificate bundle for HTTPS |
| tqdm | MPL-2.0 and MIT | Progress bars |

Because EbookLib is AGPL, anyone who distributes a combined program that
includes it takes on the AGPL's terms for that program. No built app
(`.app`) of Imprint Studio has been distributed; the source repository
imports EbookLib but does not contain it. Before a built app leaves the
owner's machines, the bundle steps in `licences.md` §3 apply (licence texts,
LGPL notices, excluding Qt Virtual Keyboard, and a decision on EbookLib).

Not shipped: ffmpeg, ffprobe and Calibre are installed by the user
(Homebrew), not bundled.

## Permissive dependencies

| Licence | Packages |
|---|---|
| Apache-2.0 | openai, anthropic, google-genai, google-api-python-client, google-auth, google-auth-oauthlib, requests, distro |
| BSD | httpx, httpcore, httpx2, httpcore2, idna, lxml, Markdown, pypdf, python-dotenv, psutil, reportlab |
| MIT | beautifulsoup4, soupsieve, annotated-types, anyio, h11, jiter, pydantic, pydantic-core, PyYAML, python-docx, python-pptx, six, sniffio (MIT or Apache-2.0), tiktoken, typing-inspection, urllib3, charset-normalizer |
| MIT-CMU (HPND) | pillow |
| Apache-2.0 and CNRI-Python | regex |
| PSF-2.0 | typing_extensions |

## Data

`config/lmarena_snapshot.json` holds public model ratings under CC BY 4.0;
its source and licence are named in the file.

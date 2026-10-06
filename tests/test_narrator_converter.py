"""
Imprint — narrator converter
============================
Type: Unit tests for EPUB reading order, resume safety, and the output format.

Three behaviours that are invisible when they break. A shuffled EPUB still
produces perfectly good audio, just in the wrong order. A resume onto edited
text still produces a file. A chapter mark at the wrong offset still opens.
None of them announce themselves, so they are pinned here.

Run with:  pytest tests/test_narrator_converter.py -v
"""

import os
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.narrator import converter


def _epub(path, sections, spine_order):
    """A minimal EPUB whose spine order differs from its file order."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml",
                    '<?xml version="1.0"?><container version="1.0" '
                    'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                    '<rootfiles><rootfile full-path="OEBPS/content.opf" '
                    'media-type="application/oebps-package+xml"/></rootfiles>'
                    '</container>')
        manifest, spine = [], []
        for item_id, filename, heading, body in sections:
            zf.writestr(f"OEBPS/{filename}",
                        f"<html><body><h1>{heading}</h1><p>{body}</p></body></html>")
            manifest.append(
                f'<item id="{item_id}" href="{filename}" '
                f'media-type="application/xhtml+xml"/>')
        for item_id in spine_order:
            spine.append(f'<itemref idref="{item_id}"/>')
        zf.writestr("OEBPS/content.opf",
                    '<?xml version="1.0"?>'
                    '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
                    'unique-identifier="id">'
                    '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
                    '<dc:identifier id="id">test</dc:identifier>'
                    '<dc:title>Test</dc:title><dc:language>en</dc:language>'
                    '</metadata>'
                    f'<manifest>{"".join(manifest)}</manifest>'
                    f'<spine>{"".join(spine)}</spine></package>')
    return path


# ── Reading order ────────────────────────────────────────────────────────────
def test_chapters_follow_the_spine_not_the_file_order(tmp_path):
    """`get_items()` returns manifest order. A book whose files are not named
    in reading order was narrated shuffled, and the audio sounded fine."""
    path = _epub(tmp_path / "b.epub", [
        ("c3", "zeta.xhtml", "Third", "gamma text"),
        ("c1", "alpha.xhtml", "First", "alpha text"),
        ("c2", "mid.xhtml", "Second", "beta text"),
    ], spine_order=["c1", "c2", "c3"])

    chapters = converter.extract_epub_chapters(path)
    assert [title for title, _ in chapters] == ["First", "Second", "Third"]
    assert "alpha text" in converter.load_text(path).split("beta text")[0]


def test_a_section_without_a_heading_still_gets_a_name(tmp_path):
    path = _epub(tmp_path / "b.epub",
                 [("c1", "a.xhtml", "", "body")], spine_order=["c1"])
    titles = [title for title, _ in converter.extract_epub_chapters(path)]
    assert titles and all(titles)


# ── Resume safety ────────────────────────────────────────────────────────────
def test_manifest_records_the_text_it_was_built_from(tmp_path):
    a = converter.build_manifest("Book", tmp_path / "b.epub", ["one", "two"])
    b = converter.build_manifest("Book", tmp_path / "b.epub", ["one", "three"])
    assert a["text_sha256"] != b["text_sha256"]


def test_edited_text_does_not_resume_onto_the_old_audio(tmp_path):
    """Same filename, same voice, same chunk size — only the text changed.
    That used to look 'compatible', so the run continued onto audio generated
    from text that no longer existed."""
    manifest_path = tmp_path / "manifest.json"
    temp_dir = tmp_path / "temp_audio"
    temp_dir.mkdir()
    source = tmp_path / "b.epub"

    converter.json_dump(manifest_path, converter.build_manifest(
        "Book", source, ["original one", "original two"]))
    stale = temp_dir / "chunk_0.mp3"
    stale.write_bytes(b"old audio")

    converter.load_or_create_manifest(
        manifest_path, "Book", source, ["edited one", "edited two"],
        temp_dir=temp_dir)

    assert not stale.exists(), "stale chunk survived a text change"


def test_an_unchanged_run_still_resumes(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    temp_dir = tmp_path / "temp_audio"
    temp_dir.mkdir()
    source = tmp_path / "b.epub"
    chunks = ["one", "two"]

    converter.json_dump(manifest_path,
                        converter.build_manifest("Book", source, chunks))
    kept = temp_dir / "chunk_0.mp3"
    kept.write_bytes(b"audio")

    converter.load_or_create_manifest(
        manifest_path, "Book", source, chunks, temp_dir=temp_dir)

    assert kept.exists(), "a resumable run threw away paid audio"


def test_the_refuse_policy_stops_instead_of_clearing(tmp_path, monkeypatch):
    """The refuse policy is for a CLI-only copy with an operator present: it
    asks rather than deciding. No shipped copy uses it since the standalone
    Audiobook Studio was merged into Imprint, but the branch stays covered."""
    monkeypatch.setattr(converter, "ON_SETTINGS_CHANGE",
                        converter.REFUSE_ON_CHANGE)
    manifest_path = tmp_path / "manifest.json"
    temp_dir = tmp_path / "temp_audio"
    temp_dir.mkdir()
    source = tmp_path / "b.epub"
    converter.json_dump(manifest_path,
                        converter.build_manifest("Book", source, ["old"]))
    kept = temp_dir / "chunk_0.mp3"
    kept.write_bytes(b"audio")

    with pytest.raises(RuntimeError, match="force-rebuild"):
        converter.load_or_create_manifest(
            manifest_path, "Book", source, ["new"], temp_dir=temp_dir)
    assert kept.exists(), "refusing should not delete anything either"


# ── Output format ────────────────────────────────────────────────────────────
def test_both_formats_are_offered_and_mp3_is_the_default():
    assert converter.AUDIO_FORMATS == ("mp3", "m4b")
    assert converter.DEFAULT_FORMAT == "mp3"


def test_chapter_metadata_places_each_chapter_at_a_measured_offset(
        tmp_path, monkeypatch):
    monkeypatch.setattr(converter, "get_audio_duration_seconds", lambda p: 2.0)
    chunks = [tmp_path / f"chunk_{i}.mp3" for i in range(4)]
    for path in chunks:
        path.write_bytes(b"x")

    written = converter.write_chapter_metadata(
        tmp_path, "Book", chunks, [("One", 0), ("Two", 2)])
    text = written.read_text()

    assert "START=0" in text and "END=4000" in text     # chunks 0–1
    assert "START=4000" in text and "END=8000" in text  # chunks 2–3
    assert "title=One" in text and "title=Two" in text


def test_m4b_really_carries_the_chapters(tmp_path):
    """End to end through real ffmpeg. The metadata file can be perfect and
    still not reach the container if the mapping flags are wrong, which is not
    visible from anything short of probing the output."""
    import json
    import shutil as _shutil
    import subprocess as _subprocess

    if not _shutil.which("ffmpeg") or not _shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe not installed")

    for index in range(2):
        _subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
             f"sine=frequency={440 + index * 220}:duration=0.5", "-q:a", "6",
             str(tmp_path / f"chunk_{index}.mp3")], check=True)

    output = tmp_path / "Book.m4b"
    converter.merge_chunks_with_ffmpeg(
        tmp_path, output, 2, [("First", 0), ("Second", 1)], converter.FORMAT_M4B)

    probe = _subprocess.run(
        ["ffprobe", "-v", "error", "-show_chapters", "-of", "json", str(output)],
        capture_output=True, text=True, check=True)
    chapters = json.loads(probe.stdout)["chapters"]

    assert [c["tags"]["title"] for c in chapters] == ["First", "Second"]
    assert output.stat().st_size > 0


def test_mp3_is_a_stream_copy_with_no_chapter_file(tmp_path):
    import shutil as _shutil
    import subprocess as _subprocess

    if not _shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")

    for index in range(2):
        _subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
             f"sine=frequency=440:duration=0.5", "-q:a", "6",
             str(tmp_path / f"chunk_{index}.mp3")], check=True)

    output = tmp_path / "Book.mp3"
    converter.merge_chunks_with_ffmpeg(
        tmp_path, output, 2, [("First", 0)], converter.FORMAT_MP3)

    assert output.is_file() and output.stat().st_size > 0
    assert not (tmp_path / converter.CHAPTER_METADATA_FILENAME).exists()


def test_a_chapter_title_cannot_break_the_metadata_file(tmp_path, monkeypatch):
    """ffmetadata is key=value; an unescaped '=' or ';' in a title truncates
    or comments out the rest of the file."""
    monkeypatch.setattr(converter, "get_audio_duration_seconds", lambda p: 1.0)
    chunk = tmp_path / "chunk_0.mp3"
    chunk.write_bytes(b"x")

    written = converter.write_chapter_metadata(
        tmp_path, "Book", [chunk], [("Chapter 1 = the start; really # honestly", 0)])
    line = [l for l in written.read_text().splitlines()
            if l.startswith("title=Chapter")][0]

    assert r"\=" in line and r"\;" in line and r"\#" in line


def test_a_line_break_in_a_title_does_not_end_the_chapter_entry():
    """ffmetadata ends a value at a carriage return as well as a newline, so a
    CRLF heading used to keep only the words before the break."""
    assert (converter.ffmetadata_escape("Chapter One\r\nThe Beginning")
            == "Chapter One The Beginning")


def test_the_merge_refuses_a_format_it_does_not_know(tmp_path, monkeypatch):
    """Anything that was not "mp3" used to take the M4B branch and be renamed
    onto whatever suffix the caller asked for."""
    monkeypatch.setattr(converter, "ensure_ffmpeg_available", lambda: "ffmpeg")
    (tmp_path / "chunk_0.mp3").write_bytes(b"x")

    with pytest.raises(ValueError, match="wav"):
        converter.merge_chunks_with_ffmpeg(tmp_path, tmp_path / "Book.wav", 1, [], "wav")


# ── Chunking per format ──────────────────────────────────────────────────────
class _WordEncoder:
    """Counts words, so a chunk limit reads as a word limit."""

    def encode(self, text):
        return text.split()


def test_mp3_keeps_whole_book_chunk_boundaries(tmp_path, monkeypatch):
    """MP3 carries no chapter marks, so it chunks the whole book in one pass —
    the boundaries every earlier version drew. Chunking it per chapter moved
    all of them, and a run paused before that change met a 'settings changed'
    rebuild on resume that threw its paid chunks away. M4B needs each chapter
    on a chunk boundary and so chunks per chapter."""
    monkeypatch.setattr(converter, "get_token_encoder", _WordEncoder)
    monkeypatch.setattr(converter, "MAX_INPUT_TOKENS_PER_CHUNK", 4)

    def fake_tts(text, path, retries=2):
        path.write_bytes(b"x")
        return True

    monkeypatch.setattr(converter, "generate_tts_chunk", fake_tts)
    monkeypatch.setattr(converter, "merge_chunks_with_ffmpeg", lambda *a, **k: None)
    chapters = [("One", "a b c"), ("Two", "d e f g h")]      # 3 + 5 words
    source = tmp_path / "b.epub"
    manifest_path = tmp_path / "manifest.json"

    def run(audio_format):
        manifest_path.unlink(missing_ok=True)
        assert converter.text_to_audio(
            chapters, source, "Book", tmp_path / f"Book.{audio_format}",
            tmp_path / "temp_audio", manifest_path, audio_format=audio_format)
        return converter.json_load(manifest_path)

    whole_book = converter.chunk_text("\n\n".join(text for _, text in chapters), 4)
    mp3 = run("mp3")
    assert mp3["total_chunks"] == len(whole_book) == 2          # eight words in fours
    assert mp3["text_sha256"] == converter.build_manifest(
        "Book", source, whole_book)["text_sha256"]             # so an old manifest still matches

    assert run("m4b")["total_chunks"] == 3                      # One: 1 chunk; Two: 2


# ── Resume safety: a chunk stopped mid-stream ────────────────────────────────
class _Stream:
    """A stand-in for the OpenAI streaming response: writes some audio, then
    does as told."""

    def __init__(self, then):
        self.then = then

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def stream_to_file(self, path):
        Path(path).write_bytes(b"\xff\xfb" * 64)
        if self.then is not None:
            raise self.then


def _client(then):
    class Speech:
        class with_streaming_response:
            @staticmethod
            def create(**kwargs):
                return _Stream(then)

    class Audio:
        speech = Speech()

    class Client:
        audio = Audio()

    return Client()


def test_a_chunk_stopped_mid_stream_is_not_resumed_as_done(tmp_path, monkeypatch):
    """Stop in the audiobook panel kills the worker. The bytes already streamed
    used to sit under the chunk's final name, and the next run took that short
    file for a finished chunk and stitched a mid-sentence cut into the book."""
    final = tmp_path / "chunk_57.mp3"
    monkeypatch.setattr(converter, "get_client", lambda: _client(KeyboardInterrupt()))

    with pytest.raises(KeyboardInterrupt):
        converter.generate_tts_chunk("text", final, retries=1)

    assert not final.exists()
    manifest = {"chunks": [{"index": 57, "filename": final.name, "status": "done"}]}
    converter.sync_manifest_with_files(manifest, tmp_path)
    assert manifest["chunks"][0]["status"] == "pending"


def test_a_finished_chunk_lands_under_its_final_name_only(tmp_path, monkeypatch):
    final = tmp_path / "chunk_0.mp3"
    monkeypatch.setattr(converter, "get_client", lambda: _client(None))

    assert converter.generate_tts_chunk("text", final, retries=1)
    assert final.stat().st_size > 0
    assert list(tmp_path.glob("*" + converter.CHUNK_PARTIAL_SUFFIX)) == []


def test_a_failed_attempt_leaves_no_partial_behind(tmp_path, monkeypatch):
    final = tmp_path / "chunk_0.mp3"
    monkeypatch.setattr(converter, "get_client", lambda: _client(RuntimeError("dropped")))
    monkeypatch.setattr(converter.time, "sleep", lambda seconds: None)

    assert not converter.generate_tts_chunk("text", final, retries=2)
    assert not final.exists()
    assert list(tmp_path.glob("*" + converter.CHUNK_PARTIAL_SUFFIX)) == []


def test_cleanup_sweeps_partial_chunks_too(tmp_path):
    temp_dir = tmp_path / "temp_audio"
    temp_dir.mkdir()
    (temp_dir / "chunk_0.mp3").write_bytes(b"x")
    (temp_dir / ("chunk_1.mp3" + converter.CHUNK_PARTIAL_SUFFIX)).write_bytes(b"x")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{}")

    converter.cleanup_after_success(temp_dir, manifest_path)

    assert not temp_dir.exists() and not manifest_path.exists()


def test_a_resume_sweeps_the_partial_a_stop_left_behind(tmp_path):
    """A kill skips the cleanup a caught failure gets, so the partial stays on
    disk; the next run should not carry it around."""
    partial = tmp_path / ("chunk_3.mp3" + converter.CHUNK_PARTIAL_SUFFIX)
    partial.write_bytes(b"x")
    manifest = converter.build_manifest("Book", tmp_path / "b.epub", ["one"])

    converter.sync_manifest_with_files(manifest, tmp_path)

    assert not partial.exists()


def test_a_manifest_from_before_partial_files_trusts_only_recorded_chunks(tmp_path):
    """Before partial files, a stop could leave a cut-short chunk under its
    final name. Such a manifest recorded a chunk as done only after its
    stream finished, so a present chunk it never recorded is the suspect one
    and is redone; the recorded ones stay."""
    (tmp_path / "chunk_0.mp3").write_bytes(b"complete")
    (tmp_path / "chunk_1.mp3").write_bytes(b"cut short")
    manifest = {"chunks": [
        {"index": 0, "filename": "chunk_0.mp3", "status": "done"},
        {"index": 1, "filename": "chunk_1.mp3", "status": "pending"},
    ]}                                                  # no "format": the old layout

    converter.sync_manifest_with_files(manifest, tmp_path)

    assert [c["status"] for c in manifest["chunks"]] == ["done", "pending"]
    assert (tmp_path / "chunk_0.mp3").exists()
    assert not (tmp_path / "chunk_1.mp3").exists()
    assert manifest["format"] == converter.MANIFEST_FORMAT

    # Under the new layout a present chunk is complete even if the manifest,
    # saved every few chunks, had not recorded it yet.
    (tmp_path / "chunk_1.mp3").write_bytes(b"complete by rename")
    manifest["chunks"][1]["status"] = "pending"
    converter.sync_manifest_with_files(manifest, tmp_path)
    assert manifest["chunks"][1]["status"] == "done"


# ── External tools ───────────────────────────────────────────────────────────
def test_calibres_epub_goes_into_the_temp_dir_and_leaves_with_it(tmp_path, monkeypatch):
    """`ebook-convert` wrote `<stem>.converted.epub` beside the audiobook, where
    nothing ever removed it. In the temp dir the usual cleanup takes it."""
    monkeypatch.setattr(converter, "ensure_ebook_convert_available", lambda: "ebook-convert")

    def fake_calibre(cmd, what):
        Path(cmd[2]).write_bytes(b"epub")
    monkeypatch.setattr(converter, "run_checked", fake_calibre)

    temp_dir = tmp_path / "temp_audio"                   # not there yet: a first run
    converted = converter.convert_mobi_to_epub(tmp_path / "Book.mobi", temp_dir)
    assert converted.parent == temp_dir and converted.exists()

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{}")
    converter.cleanup_after_success(temp_dir, manifest_path)
    assert not temp_dir.exists()


def test_tools_run_in_the_launch_environment_not_the_bundles(monkeypatch):
    """PyInstaller points the linker at the bundle's libraries and stashes the
    launch-time value as <VAR>_ORIG; a tool must get the latter back. Checked
    on a real child process, not the helper's dictionary, so `run_checked`
    forgetting to pass the environment on would fail here."""
    monkeypatch.setenv("DYLD_LIBRARY_PATH", "/Bundle/Frameworks")
    monkeypatch.setenv("DYLD_LIBRARY_PATH_ORIG", "/launch/Frameworks")
    monkeypatch.setenv("LD_LIBRARY_PATH", "/Bundle/lib")
    monkeypatch.delenv("LD_LIBRARY_PATH_ORIG", raising=False)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    # LD_LIBRARY_PATH rather than DYLD_*: macOS strips the latter from any
    # child of a system binary, which the test's Python may be.
    probe = [sys.executable, "-c",
             "import os; print(os.environ.get('LD_LIBRARY_PATH'), os.environ['PATH'])"]

    seen = converter.run_checked(probe, "probe").stdout.split()
    assert seen[0] == "/Bundle/lib"                     # from source: nothing to undo
    assert seen[1].split(os.pathsep) == [
        "/usr/bin", "/bin", "/opt/homebrew/bin", "/usr/local/bin"]
    env = converter.subprocess_env()
    assert env["DYLD_LIBRARY_PATH"] == "/launch/Frameworks"
    assert "DYLD_LIBRARY_PATH_ORIG" not in env

    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/launch/lib")
    assert converter.run_checked(probe, "probe").stdout.split()[0] == "/launch/lib"

    monkeypatch.delenv("LD_LIBRARY_PATH_ORIG")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert converter.run_checked(probe, "probe").stdout.split()[0] == "None"


def test_a_tool_finders_bare_path_hides_is_still_found(tmp_path, monkeypatch):
    """An app launched from Finder gets a PATH without Homebrew, so a tool that
    works in Terminal is invisible to `shutil.which` alone."""
    homebrew = tmp_path / "homebrew"
    homebrew.mkdir()
    ffmpeg = homebrew / "ffmpeg"
    ffmpeg.write_text("#!/bin/sh\n")
    ffmpeg.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path / "nowhere"))
    monkeypatch.setattr(converter, "EXTRA_PATH_ENTRIES", (str(homebrew),))

    assert converter.ensure_ffmpeg_available() == str(ffmpeg)
    with pytest.raises(RuntimeError, match="ffprobe was not found"):
        converter.ensure_ffprobe_available()


def test_calibres_app_bundle_is_a_fallback_for_ebook_convert(tmp_path, monkeypatch):
    """Calibre's installer ships an app bundle and no PATH entry."""
    in_app = tmp_path / "calibre.app" / "ebook-convert"
    in_app.parent.mkdir()
    in_app.write_text("#!/bin/sh\n")
    monkeypatch.setenv("PATH", str(tmp_path / "nowhere"))
    monkeypatch.setattr(converter, "EXTRA_PATH_ENTRIES", ())
    monkeypatch.setattr(converter, "EBOOK_CONVERT_IN_APP",
                        str(in_app.relative_to(in_app.anchor)))

    with pytest.raises(RuntimeError, match="ebook-convert was not found"):
        converter.ensure_ebook_convert_available()       # present, not executable
    in_app.chmod(0o755)
    assert converter.ensure_ebook_convert_available() == str(in_app)


def test_a_failing_tool_reports_what_it_said(tmp_path):
    with pytest.raises(RuntimeError, match="ffprobe failed .*exit code 3") as info:
        converter.run_checked(
            [sys.executable, "-c", "import sys; sys.stderr.write('no such stream'); sys.exit(3)"],
            "ffprobe")
    assert "no such stream" in str(info.value)

    with pytest.raises(RuntimeError, match="ffmpeg could not be started"):
        converter.run_checked([str(tmp_path / "missing-ffmpeg")], "ffmpeg")

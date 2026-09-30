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
    """Audiobook Studio runs the same converter with ON_SETTINGS_CHANGE set to
    refuse: a CLI operator is present, so it asks rather than deciding."""
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

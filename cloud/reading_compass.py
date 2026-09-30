"""Private Reading Compass API and long-running Imprint Narrator worker.

Deploy the web service and the worker as separate Cloud Run resources using
the same image. All Drive calls run as the signed-in owner, not as the Cloud
Run service account. The latter only launches jobs and accesses Firestore.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import google.auth
from cryptography.fernet import Fernet
from flask import Flask, Response, jsonify, make_response, redirect, request, send_from_directory, stream_with_context
from google.auth.transport.requests import Request as AuthRequest
from google.cloud import firestore
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaInMemoryUpload, MediaIoBaseDownload
from itsdangerous import BadSignature, URLSafeTimedSerializer
import requests
from werkzeug.exceptions import HTTPException

from cloud.contracts import ALLOWED_EXTENSIONS, ebook_parts, progress_filename, updated_progress


DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
MIME_FOLDER = "application/vnd.google-apps.folder"
MAX_MEDIA_CHUNK = 8 * 1024 * 1024
VOICES = {"alloy", "verse", "marin", "coral", "sage"}
app = Flask(__name__)


def config(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing configuration: {name}")
    return value


def signer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(config("SESSION_SECRET"))


def db():
    return firestore.Client()


def users():
    return db().collection("reading_compass_users")


def jobs():
    return db().collection("reading_compass_jobs")


def cipher():
    return Fernet(config("TOKEN_ENCRYPTION_KEY"))


def owner_id():
    cookie = request.cookies.get("rc_session", "")
    try:
        user_id = signer().loads(cookie, salt="reading-compass", max_age=60 * 60 * 24 * 30)
    except BadSignature:
        return None
    return user_id if users().document(user_id).get().exists else None


def require_owner():
    user_id = owner_id()
    if not user_id:
        raise ApiError(401, "Connect your Google Drive account first.")
    return user_id


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


@app.errorhandler(ApiError)
def api_error(exc):
    return jsonify(error=str(exc)), exc.status


@app.errorhandler(Exception)
def server_error(exc):
    if isinstance(exc, HTTPException):
        return jsonify(error=exc.description), exc.code
    app.logger.exception("Reading Compass request failed")
    return jsonify(error="The cloud service could not complete this request."), 500


def google_credentials(user_id: str) -> Credentials:
    record = users().document(user_id).get().to_dict() or {}
    encrypted = record.get("refresh_token")
    if not encrypted:
        raise ApiError(401, "Reconnect Google Drive to continue.")
    refresh_token = cipher().decrypt(encrypted.encode()).decode()
    credentials = Credentials(
        None, refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config("GOOGLE_CLIENT_ID"),
        client_secret=config("GOOGLE_CLIENT_SECRET"),
        scopes=[DRIVE_SCOPE],
    )
    credentials.refresh(AuthRequest())
    return credentials


def drive(user_id: str):
    return build("drive", "v3", credentials=google_credentials(user_id), cache_discovery=False)


def drive_list(service, query: str, fields="id,name,mimeType,size,parents"):
    found = []
    page = None
    while True:
        result = service.files().list(
            q=query, spaces="drive", pageSize=1000, pageToken=page,
            fields=f"nextPageToken,files({fields})",
        ).execute()
        found.extend(result.get("files", []))
        page = result.get("nextPageToken")
        if not page:
            return found


def children(service, parent_id: str):
    return drive_list(service, f"'{parent_id}' in parents and trashed = false")


def named_child(service, parent_id: str, name: str, mime: str | None = None):
    matches = [item for item in children(service, parent_id)
               if item["name"] == name and (mime is None or item["mimeType"] == mime)]
    if len(matches) > 1:
        raise ApiError(409, f"More than one Drive item is named {name!r} in this folder.")
    return matches[0] if matches else None


def root_folder(service, name: str, create=False):
    folder = named_child(service, "root", name, MIME_FOLDER)
    if not folder and create:
        folder = service.files().create(
            body={"name": name, "mimeType": MIME_FOLDER, "parents": ["root"]},
            fields="id,name,mimeType",
        ).execute()
    if not folder:
        raise ApiError(404, f"Create a folder named {name!r} in My Drive first.")
    return folder


def ensure_folder(service, parent: str, name: str):
    folder = named_child(service, parent, name, MIME_FOLDER)
    if folder:
        return folder
    return service.files().create(
        body={"name": name, "mimeType": MIME_FOLDER, "parents": [parent]},
        fields="id,name,mimeType",
    ).execute()


def relative_file(service, path: str):
    try:
        parts = ebook_parts(path)
    except ValueError as exc:
        raise ApiError(400, str(exc)) from exc
    parent = root_folder(service, "ebooks")["id"]
    for part in parts[:-1]:
        folder = named_child(service, parent, part, MIME_FOLDER)
        if not folder:
            raise ApiError(404, "This ebook is no longer in the Drive ebooks folder.")
        parent = folder["id"]
    item = named_child(service, parent, parts[-1])
    if not item or item["mimeType"] == MIME_FOLDER:
        raise ApiError(404, "This ebook is no longer in the Drive ebooks folder.")
    return item


def audio_file(service, file_id: str):
    if not re.fullmatch(r"[A-Za-z0-9_-]{10,200}", file_id):
        raise ApiError(400, "Invalid audio file ID.")
    item = service.files().get(fileId=file_id, fields="id,name,size,mimeType,parents").execute()
    if not item.get("name", "").lower().endswith(".mp3"):
        raise ApiError(400, "Choose an MP3 audiobook.")
    root = root_folder(service, "audiobooks - gdrive")["id"]
    parents = item.get("parents", [])
    for _ in range(8):
        if root in parents:
            return item
        if len(parents) != 1:
            break
        folder = service.files().get(fileId=parents[0], fields="id,parents,mimeType").execute()
        if folder.get("mimeType") != MIME_FOLDER:
            break
        parents = folder.get("parents", [])
    raise ApiError(403, "This audiobook is outside your output folder.")


def progress_name(item):
    return progress_filename(item["name"], item.get("size", "0"))


def progress_location(service, item):
    root = root_folder(service, "audiobooks - gdrive")["id"]
    folder = ensure_folder(service, root, "Imprint Progress")
    return folder["id"], named_child(service, folder["id"], progress_name(item))


def write_progress(service, item, data):
    folder_id, existing = progress_location(service, item)
    media_body = MediaInMemoryUpload(json.dumps(data, ensure_ascii=False).encode(),
                                     mimetype="application/json", resumable=False)
    if existing:
        service.files().update(fileId=existing["id"], media_body=media_body).execute()
    else:
        service.files().create(body={"name": progress_name(item), "parents": [folder_id]},
                               media_body=media_body, fields="id").execute()


def get_progress(service, item):
    _, record = progress_location(service, item)
    if not record:
        return {"version": 1, "file_name": item["name"], "position_ms": 0,
                "duration_ms": 0, "finished": False, "marks": []}
    content = service.files().get_media(fileId=record["id"]).execute()
    data = json.loads(content)
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ApiError(409, "This audiobook has an invalid progress file.")
    return data


@app.get("/auth/start")
def auth_start():
    state = os.urandom(24).hex()
    next_path = request.args.get("next", "/")
    if next_path not in ("/", "/cloud/app"):
        raise ApiError(400, "Invalid return page.")
    params = {
        "client_id": config("GOOGLE_CLIENT_ID"),
        "redirect_uri": config("OAUTH_REDIRECT_URI"),
        "response_type": "code", "scope": f"openid email {DRIVE_SCOPE}",
        "access_type": "offline", "prompt": "consent", "state": state,
    }
    response = make_response(redirect("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)))
    response.set_cookie("rc_oauth_state", state, max_age=600, httponly=True, secure=True, samesite="Lax")
    response.set_cookie("rc_oauth_next", next_path, max_age=600, httponly=True, secure=True, samesite="Lax")
    return response


@app.get("/auth/callback")
def auth_callback():
    state = request.args.get("state", "")
    if not state or state != request.cookies.get("rc_oauth_state"):
        raise ApiError(400, "Google sign-in expired. Start again from the dashboard.")
    code = request.args.get("code", "")
    if not code:
        raise ApiError(400, "Google Drive access was not granted.")
    response = requests.post("https://oauth2.googleapis.com/token", data={
        "code": code, "client_id": config("GOOGLE_CLIENT_ID"),
        "client_secret": config("GOOGLE_CLIENT_SECRET"),
        "redirect_uri": config("OAUTH_REDIRECT_URI"), "grant_type": "authorization_code",
    }, timeout=30)
    response.raise_for_status()
    token = response.json()
    info_response = requests.get("https://openidconnect.googleapis.com/v1/userinfo",
                                 headers={"Authorization": f"Bearer {token['access_token']}"}, timeout=30)
    info_response.raise_for_status()
    info = info_response.json()
    if not info.get("email_verified") or info.get("email", "").lower() != config("ALLOWED_EMAIL").lower():
        raise ApiError(403, "This dashboard is connected to a different Google account.")
    user_id = info["sub"]
    old = users().document(user_id).get().to_dict() or {}
    refresh = token.get("refresh_token")
    if refresh:
        encrypted = cipher().encrypt(refresh.encode()).decode()
    else:
        encrypted = old.get("refresh_token")
    if not encrypted:
        raise ApiError(400, "Google did not return offline access. Reconnect and approve access.")
    users().document(user_id).set({"email": info["email"], "refresh_token": encrypted}, merge=True)
    next_path = request.cookies.get("rc_oauth_next", "/")
    if next_path not in ("/", "/cloud/app"):
        next_path = "/"
    result = make_response(redirect(config("DASHBOARD_URL").rstrip("/") + next_path))
    result.set_cookie("rc_session", signer().dumps(user_id, salt="reading-compass"),
                      max_age=60 * 60 * 24 * 30, httponly=True, secure=True, samesite="Lax")
    result.delete_cookie("rc_oauth_state")
    result.delete_cookie("rc_oauth_next")
    return result


@app.get("/app")
def web_agent():
    return send_from_directory(Path(__file__).parent / "web", "index.html")


@app.get("/app.js")
def web_agent_js():
    return send_from_directory(Path(__file__).parent / "web", "app.js")


@app.get("/app.css")
def web_agent_css():
    return send_from_directory(Path(__file__).parent / "web", "app.css")


@app.get("/api/session")
def session():
    user_id = owner_id()
    if not user_id:
        return jsonify(connected=False)
    return jsonify(connected=True, email=(users().document(user_id).get().to_dict() or {}).get("email"))


@app.get("/api/books")
def list_books():
    service = drive(require_owner())
    root = root_folder(service, "ebooks")["id"]
    found = []
    pending = [(root, "", 0)]
    while pending:
        folder_id, prefix, depth = pending.pop()
        if depth > 12 or len(found) > 10000:
            raise ApiError(409, "The ebooks folder is too large to list safely.")
        for item in children(service, folder_id):
            path = f"{prefix}{item['name']}"
            if item["mimeType"] == MIME_FOLDER:
                pending.append((item["id"], path + "/", depth + 1))
            elif Path(item["name"]).suffix.lower() in ALLOWED_EXTENSIONS:
                found.append({"drive_path": path, "name": item["name"],
                              "size": item.get("size", "0")})
    return jsonify(books=sorted(found, key=lambda x: x["name"].lower()))


def download_book(service, source, destination: Path):
    with destination.open("wb") as source_file:
        downloader = MediaIoBaseDownload(
            source_file, service.files().get_media(fileId=source["id"]),
            chunksize=4 * 1024 * 1024,
        )
        completed = False
        while not completed:
            _, completed = downloader.next_chunk()


@app.post("/api/estimate")
def estimate_book():
    service = drive(require_owner())
    payload = request.get_json(silent=True) or {}
    path = payload.get("drive_path")
    if not isinstance(path, str):
        raise ApiError(400, "Choose an ebook first.")
    source = relative_file(service, path)
    if int(source.get("size", "0")) > 200 * 1024 * 1024:
        raise ApiError(413, "This ebook is too large to estimate online.")
    from services.narrator.converter import (
        count_text_tokens, estimate_audio_seconds_from_text,
        estimate_audio_tokens_from_seconds, estimate_costs_usd, load_text,
    )
    with tempfile.TemporaryDirectory(prefix="reading-compass-estimate-") as temp:
        path_on_disk = Path(temp) / source["name"]
        download_book(service, source, path_on_disk)
        raw = load_text(path_on_disk, work_dir=Path(temp))
        if not raw.strip():
            raise ApiError(422, "No readable text was found in this ebook.")
        tokens = count_text_tokens(raw)
        seconds = estimate_audio_seconds_from_text(raw)
        cost = estimate_costs_usd(tokens, estimate_audio_tokens_from_seconds(seconds))
    return jsonify(minutes=round(seconds / 60, 1),
                   estimated_usd=round(cost["total_usd"], 2),
                   characters=len(raw),
                   pricing_note="Estimate from Imprint Narrator; actual API charges may differ.")


@app.post("/api/jobs")
def enqueue():
    user_id = require_owner()
    payload = request.get_json(silent=True) or {}
    path = payload.get("drive_path")
    if not isinstance(path, str):
        raise ApiError(400, "Choose an ebook from the dashboard.")
    service = drive(user_id)
    source = relative_file(service, path)
    voice = payload.get("voice", "alloy")
    if voice not in VOICES:
        raise ApiError(400, "Choose a supported narration voice.")
    try:
        chunk_tokens = int(payload.get("chunk_tokens", 1400))
    except (TypeError, ValueError):
        raise ApiError(400, "Chunk size must be a number.")
    if chunk_tokens < 300 or chunk_tokens > 1500:
        raise ApiError(400, "Chunk size must be between 300 and 1500 tokens.")
    key = hashlib.sha256(f"{user_id}\n{source['id']}".encode()).hexdigest()
    ref = jobs().document(key)
    previous = ref.get().to_dict() or {}
    if previous.get("status") in ("queued", "running", "finished"):
        return jsonify(id=key, status=previous["status"], already_exists=True)
    for snapshot in jobs().where("user_id", "==", user_id).stream():
        if snapshot.id != key and (snapshot.to_dict() or {}).get("status") in ("queued", "running"):
            raise ApiError(409, "Wait for the current audiobook to finish before queuing another.")
    ref.set({"user_id": user_id, "drive_path": path, "source_id": source["id"],
             "source_name": source["name"], "voice": voice,
             "chunk_tokens": chunk_tokens, "status": "queued",
             "updated_at": firestore.SERVER_TIMESTAMP})
    try:
        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        credentials.refresh(AuthRequest())
        endpoint = f"https://run.googleapis.com/v2/{config('CLOUD_RUN_JOB')}:run"
        result = requests.post(endpoint, json={"overrides": {"containerOverrides": [
            {"env": [{"name": "RC_JOB_ID", "value": key}]}]}},
            headers={"Authorization": f"Bearer {credentials.token}"}, timeout=30)
        result.raise_for_status()
        ref.set({"operation": result.json().get("name", "")}, merge=True)
    except Exception:
        ref.set({"status": "failed", "error": "Could not start the cloud converter."}, merge=True)
        raise
    return jsonify(id=key, status="queued"), 202


@app.get("/api/jobs")
def list_jobs():
    user_id = require_owner()
    entries = []
    for snapshot in jobs().where("user_id", "==", user_id).stream():
        value = snapshot.to_dict()
        entries.append({"id": snapshot.id, "drive_path": value.get("drive_path"),
                        "status": value.get("status"), "error": value.get("error", ""),
                        "voice": value.get("voice", "alloy"),
                        "audio_id": value.get("audio_id")})
    return jsonify(jobs=entries)


@app.get("/api/library")
def library():
    user_id = require_owner()
    service = drive(user_id)
    root = root_folder(service, "audiobooks - gdrive")["id"]
    items = []
    pending = [(root, 0)]
    while pending:
        folder_id, depth = pending.pop()
        if depth > 8 or len(items) > 5000:
            raise ApiError(409, "The audiobook folder is too large to list safely.")
        for item in children(service, folder_id):
            if item["mimeType"] == MIME_FOLDER and item["name"] != "Imprint Progress":
                pending.append((item["id"], depth + 1))
            elif item["name"].lower().endswith(".mp3"):
                items.append({"id": item["id"], "name": item["name"],
                              "size": item.get("size", "0")})
    return jsonify(audiobooks=sorted(items, key=lambda x: x["name"].lower()))


@app.get("/api/audio/<file_id>")
def media(file_id):
    user_id = require_owner()
    service = drive(user_id)
    item = audio_file(service, file_id)
    credentials = google_credentials(user_id)
    headers = {"Authorization": f"Bearer {credentials.token}"}
    requested_range = request.headers.get("Range", "")
    if requested_range:
        match = re.fullmatch(r"bytes=(\d*)-(\d*)", requested_range)
        if not match or not any(match.groups()):
            raise ApiError(416, "Unsupported audio byte range.")
        size = int(item.get("size", "0"))
        if not match.group(1):
            if not size:
                raise ApiError(416, "Audio size is unavailable.")
            requested_bytes = min(int(match.group(2)), MAX_MEDIA_CHUNK)
            start = max(0, size - requested_bytes)
            requested_end = size - 1
        else:
            start = int(match.group(1))
            requested_end = int(match.group(2)) if match.group(2) else start + MAX_MEDIA_CHUNK - 1
        if size and start >= size:
            raise ApiError(416, "Audio byte range is past the end of this file.")
        if requested_end < start:
            raise ApiError(416, "Invalid audio byte range.")
        end = min(requested_end, start + MAX_MEDIA_CHUNK - 1)
        if size:
            end = min(end, size - 1)
        headers["Range"] = f"bytes={start}-{end}"
    upstream = requests.get(f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media",
                            headers=headers, stream=True, timeout=60)
    if upstream.status_code not in (200, 206):
        upstream.close()
        raise ApiError(502, "Could not stream this audiobook from Drive.")

    def chunks():
        try:
            yield from upstream.iter_content(chunk_size=256 * 1024)
        finally:
            upstream.close()

    result = Response(stream_with_context(chunks()), status=upstream.status_code,
                      content_type="audio/mpeg")
    for key in ("Content-Length", "Content-Range", "Accept-Ranges"):
        if key in upstream.headers:
            result.headers[key] = upstream.headers[key]
    result.headers["Cache-Control"] = "private, no-store"
    return result


@app.get("/api/progress/<file_id>")
def progress_get(file_id):
    service = drive(require_owner())
    return jsonify(get_progress(service, audio_file(service, file_id)))


@app.put("/api/progress/<file_id>")
def progress_put(file_id):
    service = drive(require_owner())
    item = audio_file(service, file_id)
    data = request.get_json(silent=True) or {}
    try:
        position = max(0, int(data["position_ms"]))
        duration = max(0, int(data.get("duration_ms", 0)))
    except (ValueError, TypeError, KeyError):
        raise ApiError(400, "Invalid listening position.")
    current = updated_progress(
        get_progress(service, item), item["name"], position, duration,
        str(data.get("title") or item["name"]),
        datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    write_progress(service, item, current)
    return jsonify(ok=True)


@app.post("/api/marks/<file_id>")
def mark_add(file_id):
    service = drive(require_owner())
    item = audio_file(service, file_id)
    payload = request.get_json(silent=True) or {}
    try:
        position = int(payload["position_ms"])
    except (KeyError, TypeError, ValueError):
        raise ApiError(400, "Choose a valid position for the mark.")
    title = str(payload.get("title", "")).strip()[:100]
    if position < 0 or not title:
        raise ApiError(400, "A mark needs a title and a non-negative position.")
    record = get_progress(service, item)
    marks = [mark for mark in record.get("marks", [])
             if int(mark.get("position_ms", -1)) != position]
    marks.append({"position_ms": position, "title": title,
                  "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    record["marks"] = sorted(marks, key=lambda mark: mark["position_ms"])
    write_progress(service, item, record)
    return jsonify(marks=record["marks"])


@app.delete("/api/marks/<file_id>/<int:position>")
def mark_delete(file_id, position):
    service = drive(require_owner())
    item = audio_file(service, file_id)
    record = get_progress(service, item)
    record["marks"] = [mark for mark in record.get("marks", [])
                       if int(mark.get("position_ms", -1)) != position]
    write_progress(service, item, record)
    return jsonify(marks=record["marks"])


def run_worker():
    """Cloud Run Job entry point. One ebook per execution."""
    job_id = config("RC_JOB_ID")
    ref = jobs().document(job_id)
    record = ref.get().to_dict()
    if not record or record.get("status") not in ("queued", "running"):
        raise RuntimeError("This conversion request no longer exists")
    ref.set({"status": "running", "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
    try:
        from services.narrator.converter import clean_name, convert

        user_id = record["user_id"]
        service = drive(user_id)
        # Re-resolve the path to prevent stale or moved file IDs from being used.
        source = relative_file(service, record["drive_path"])
        if source["id"] != record["source_id"]:
            raise RuntimeError("The selected ebook changed in Drive; queue it again")
        with tempfile.TemporaryDirectory(prefix="reading-compass-") as temp:
            source_path = Path(temp) / source["name"]
            output = Path(temp) / "output"
            download_book(service, source, source_path)
            if not convert(input=str(source_path), output=str(output),
                           voice=record.get("voice", "alloy"),
                           chunk_tokens=int(record.get("chunk_tokens", 1400))):
                raise RuntimeError("Imprint Narrator could not convert this ebook")
            book_name = clean_name(source_path.name)
            audio_path = output / book_name / f"{book_name}.mp3"
            if not audio_path.is_file():
                raise RuntimeError("Imprint Narrator produced no MP3")
            root = root_folder(service, "audiobooks - gdrive", create=True)
            folder = ensure_folder(service, root["id"], book_name)
            existing = named_child(service, folder["id"], audio_path.name)
            upload = MediaFileUpload(str(audio_path), mimetype="audio/mpeg", resumable=True)
            if existing:
                result = service.files().update(fileId=existing["id"], media_body=upload,
                                                fields="id,name,size").execute()
            else:
                result = service.files().create(
                    body={"name": audio_path.name, "parents": [folder["id"]]},
                    media_body=upload, fields="id,name,size").execute()
        ref.set({"status": "finished", "audio_id": result["id"],
                 "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
    except Exception as exc:
        ref.set({"status": "failed", "error": str(exc)[:300],
                 "updated_at": firestore.SERVER_TIMESTAMP}, merge=True)
        raise


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "worker":
        run_worker()
    else:
        raise SystemExit("Use gunicorn cloud.reading_compass:app or python -m cloud.reading_compass worker")

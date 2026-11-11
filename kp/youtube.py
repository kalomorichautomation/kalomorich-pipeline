"""YouTube Data API v3: upload, schedule, thumbnail, playlist.
Credentials come from environment variables (GitHub Actions secrets), never from files in the repo."""
import os
import time

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]


def client():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload(yt, path, meta, publish_at=None, category="24", synthetic=False):
    """Upload as private; if publish_at (RFC3339 UTC) is given, YouTube publishes it then."""
    status = {"privacyStatus": "private", "selfDeclaredMadeForKids": False}
    if synthetic:
        status["containsSyntheticMedia"] = True              # realistic AI-generated scene disclosure
    if publish_at:
        status["publishAt"] = publish_at
    body = {
        "snippet": {"title": meta["title"], "description": meta["description"],
                    "tags": meta["tags"], "categoryId": category, "defaultLanguage": "en"},
        "status": status,
    }
    media = MediaFileUpload(path, mimetype="video/mp4", chunksize=64 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp, tries = None, 0
    while resp is None:
        try:
            st, resp = req.next_chunk()
            if st:
                print(f"  uploaded {int(st.progress() * 100)}%", flush=True)
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504) and tries < 8:
                tries += 1; time.sleep(2 ** tries); continue
            raise
    return resp["id"]


def set_thumbnail(yt, video_id, jpg):
    try:
        yt.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(jpg, mimetype="image/jpeg")).execute()
        return True
    except HttpError as e:          # custom thumbnails need a phone-verified channel
        print(f"  thumbnail not set: {e}")
        return False


def add_to_playlist(yt, video_id, title):
    pid = None
    req = yt.playlists().list(part="snippet", mine=True, maxResults=50)
    while req is not None and pid is None:
        res = req.execute()
        for p in res.get("items", []):
            if p["snippet"]["title"] == title:
                pid = p["id"]; break
        req = yt.playlists().list_next(req, res)
    if pid is None:
        pid = yt.playlists().insert(part="snippet,status", body={
            "snippet": {"title": title, "description": f"{title} by Kalomorich Productions."},
            "status": {"privacyStatus": "public"}}).execute()["id"]
    yt.playlistItems().insert(part="snippet", body={
        "snippet": {"playlistId": pid, "resourceId": {"kind": "youtube#video", "videoId": video_id}}}).execute()
    return pid

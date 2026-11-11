"""Build a long video from a short seamless loop + a music loop stored as GitHub release assets,
then upload it to YouTube, scheduled. Metadata lives in videos/<tag>.json.

  python upload_prepared.py <tag> <assets dir>
"""
import datetime as dt
import json
import os
import subprocess
import sys

from kp import youtube

tag, src = sys.argv[1], sys.argv[2]
meta = json.load(open(f"videos/{tag}.json"))
hours = float(meta.get("hours", 3))
secs = int(hours * 3600)

when = meta["publish_at"]
t = dt.datetime.fromisoformat(when.replace("Z", "+00:00"))
if t <= dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=15):
    raise SystemExit(f"publish_at {when} is in the past or too soon - update videos/{tag}.json")

loop, music, thumb = (os.path.join(src, meta[k]) for k in ("loop_file", "music_file", "thumbnail_file"))
for f in (loop, music, thumb):
    if not os.path.exists(f):
        raise SystemExit(f"missing release asset: {f}")

out = "out/video.mp4"
os.makedirs("out", exist_ok=True)
subprocess.run([
    "ffmpeg", "-v", "error", "-y", "-stream_loop", "-1", "-i", loop, "-stream_loop", "-1", "-i", music,
    "-t", str(secs), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
    "-af", f"afade=t=in:d=3,afade=t=out:st={secs - 10}:d=10", "-c:a", "aac", "-b:a", "192k",
    "-movflags", "+faststart", out], check=True)
print("built", os.path.getsize(out) // 2**20, "MB", flush=True)

yt = youtube.client()
vid = youtube.upload(yt, out, meta, publish_at=when, category=meta.get("category", "10"),
                     synthetic=meta.get("synthetic", True))
print("uploaded: https://youtu.be/" + vid, "publishes", when, flush=True)
result = {"tag": tag, "video_id": vid, "publish_at": when, "title": meta["title"]}
os.makedirs("out", exist_ok=True)
json.dump(result, open("out/result.json", "w"), indent=2)
for step, fn in (("thumbnail", lambda: youtube.set_thumbnail(yt, vid, thumb)),
                 ("playlist", lambda: youtube.add_to_playlist(yt, vid, meta["playlist"]))):
    try:
        result[step] = fn()
    except Exception as e:
        result[step] = None
        print(f"  {step} step failed: {e}", flush=True)
json.dump(result, open("out/result.json", "w"), indent=2)
summ = os.environ.get("GITHUB_STEP_SUMMARY")
if summ:
    with open(summ, "a") as f:
        f.write(f"### {meta['title']}\n\n- Video: https://youtu.be/{vid}\n- Publishes: {when}\n"
                f"- Thumbnail set: {result.get('thumbnail')}  Playlist: {result.get('playlist')}\n")

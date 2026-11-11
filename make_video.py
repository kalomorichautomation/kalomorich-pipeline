"""Make one Kalomorich Productions video end to end and (optionally) schedule it on YouTube.

  python make_video.py                       # today's seed, 1 hour, upload + schedule 5 PM New York
  python make_video.py --no-upload --minutes 1 --cycle-seconds 20   # quick local test
"""
import argparse
import datetime as dt
import glob
import json
import os
import subprocess
import sys
from zoneinfo import ZoneInfo

from kp import audio, meta, thumb, visual

PLAYLIST = "Trippy Visuals"

# The first video, exactly as approved on Nov 10 (look, music, title, thumbnail).
FIRST_VIDEO = {
    "look": {"seed": 5, "palette": "Neon", "seg": 12, "cx": 0.78, "cy": 0.58, "spin_frames": 300, "palette_cycles": 3},
    "music_seed": 5, "arrange_seed": 42,
    "title": "Trippy Fractal Mandala | 1 Hour Psychedelic Visuals & Music",
    "thumb": {"frame": 75, "palette": "Ocean", "text": "LOOK CLOSER"},
}


def font():
    for p in ["fonts/Poppins-Bold.ttf", *glob.glob("/usr/share/fonts/**/DejaVuSans-Bold.ttf", recursive=True)]:
        if os.path.exists(p):
            return p
    raise FileNotFoundError("no bold font found")


def assemble(cycle, track, out, seconds):
    """Loop the visual cycle to full length with a slow hue drift, add the soundtrack."""
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", cycle, "-i", track,
        "-t", str(seconds), "-map", "0:v", "-map", "1:a",
        "-vf", f"hue=H=2*PI*t/{seconds}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-maxrate", "12M", "-bufsize", "24M",
        "-pix_fmt", "yuv420p", "-af", "volume=-2.5dB", "-c:a", "aac", "-b:a", "256k",
        "-movflags", "+faststart", out + ".tmp.mp4"], check=True)
    os.replace(out + ".tmp.mp4", out)


def publish_time(spec):
    """'now' -> None (upload private, no schedule); 'auto' -> 5 PM New York; or any ISO date-time.
    Returns an RFC3339 UTC string YouTube accepts, or raises a clear error before any rendering."""
    s = (spec or "").strip().lower()
    if s in ("", "now", "private", "none"):
        return None
    ny = ZoneInfo("America/New_York")
    now = dt.datetime.now(dt.timezone.utc)
    if s == "auto":
        t = dt.datetime.now(ny).replace(hour=17, minute=0, second=0, microsecond=0)
        if t <= now + dt.timedelta(minutes=30):
            t += dt.timedelta(days=1)
    else:
        try:
            t = dt.datetime.fromisoformat(spec.strip().replace("Z", "+00:00"))
        except ValueError:
            raise SystemExit(f"publish_at '{spec}' not understood: use now, auto, or e.g. 2026-11-10T17:00-05:00")
        if t.tzinfo is None:
            t = t.replace(tzinfo=ny)          # bare times are New York time
    t = t.astimezone(dt.timezone.utc)
    if t <= now + dt.timedelta(minutes=15):
        raise SystemExit(f"publish_at {t:%Y-%m-%d %H:%M} UTC is in the past or too soon")
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=(dt.date.today() - dt.date(2026, 1, 1)).days)
    ap.add_argument("--minutes", type=int, default=60)
    ap.add_argument("--cycle-seconds", type=int, default=240)
    ap.add_argument("--publish-at", default="auto", help="'auto' (5 PM New York), 'now', or RFC3339 UTC")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--out", default="out")
    ap.add_argument("--preset", default="", help="'first' = the approved first video")
    a = ap.parse_args()
    a.cycle_seconds = min(a.cycle_seconds, a.minutes * 60)   # short test runs render a short cycle

    os.makedirs(a.out, exist_ok=True)
    when = None if a.no_upload else publish_time(a.publish_at)     # fail fast, before rendering
    print("publish at:", when or "not scheduled (private)", flush=True)
    p = visual.params_for(a.seed)
    m = meta.for_video(a.seed, p["palette"])
    music_seed, arrange_seed = a.seed, None
    if a.preset == "first":
        p = dict(FIRST_VIDEO["look"])
        m = meta.for_video(0, "Neon")
        m["title"] = FIRST_VIDEO["title"]
        m["description"] = m["description"].replace("A neon fractal", "A fractal")
        m["thumb_text"] = FIRST_VIDEO["thumb"]["text"]
        music_seed, arrange_seed = FIRST_VIDEO["music_seed"], FIRST_VIDEO["arrange_seed"]
    print("look:", json.dumps(p)); print("title:", m["title"]); sys.stdout.flush()

    cycle = visual.render_cycle(p, f"{a.out}/cycle.mp4", seconds=a.cycle_seconds)
    print("visual cycle rendered", flush=True)
    track = audio.soundtrack(f"{a.out}/track.wav", seed=music_seed, minutes=a.minutes,
                             transpose=0 if a.preset == "first" else [0, 2, -2, 3, -3][a.seed % 5],
                             arrange_seed=arrange_seed)
    print("soundtrack done", flush=True)
    video = f"{a.out}/video.mp4"
    assemble(cycle, track, video, a.minutes * 60)
    print("assembled", os.path.getsize(video) // 2**20, "MB", flush=True)

    n = visual.FPS * a.cycle_seconds
    if a.preset == "first":                  # the blue "LOOK CLOSER" thumbnail picked on Nov 10
        visual.still(p, FIRST_VIDEO["thumb"]["frame"], n, f"{a.out}/still.png")
        jpg = thumb.make(f"{a.out}/still.png", f"{a.out}/thumb.jpg", m["thumb_text"],
                         FIRST_VIDEO["thumb"]["palette"], font(), crop=(320, 180, 1600, 900))
    else:
        visual.still(p, n // 3, n, f"{a.out}/still.png")
        jpg = thumb.make(f"{a.out}/still.png", f"{a.out}/thumb.jpg", m["thumb_text"], p["palette"], font())

    result = {"seed": a.seed, "look": p, "meta": m}
    if not a.no_upload:
        from kp import youtube
        yt = youtube.client()
        vid = youtube.upload(yt, video, m, publish_at=when)
        print("uploaded:", f"https://youtu.be/{vid}", "scheduled for", when or "now (private)", flush=True)
        result.update(video_id=vid, publish_at=when)
        with open(f"{a.out}/result.json", "w") as f:      # record the upload before any optional step can fail
            json.dump(result, f, indent=2)
        try:
            result["thumbnail"] = youtube.set_thumbnail(yt, vid, jpg)
        except Exception as e:
            result["thumbnail"] = False; print("  thumbnail step failed:", e, flush=True)
        try:
            result["playlist"] = youtube.add_to_playlist(yt, vid, PLAYLIST)
        except Exception as e:
            result["playlist"] = None; print("  playlist step failed:", e, flush=True)
    with open(f"{a.out}/result.json", "w") as f:
        json.dump(result, f, indent=2)
    summ = os.environ.get("GITHUB_STEP_SUMMARY")
    if summ:
        with open(summ, "a") as f:
            f.write(f"### {m['title']}\n\n- Look: {p['palette']}, {p['seg']} segments, seed {a.seed}\n"
                    f"- Thumbnail text: {m['thumb_text']}\n")
            if "video_id" in result:
                f.write(f"- Video: https://youtu.be/{result['video_id']} (publishes {result['publish_at']})\n"
                        f"- Thumbnail set: {result.get('thumbnail')}  Playlist: {result.get('playlist')}\n")


if __name__ == "__main__":
    main()

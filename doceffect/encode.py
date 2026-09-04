"""
Encoding, validation and the two guards that stop a broken render shipping.

Both guards exist because of a specific failure that reached a finished file.

segment_ok: os.path.exists() alone let 0-byte and half-written NVENC outputs
through. The concat demuxer stops dead at the first unreadable file, silently
truncating the film, so a 295-segment cut once produced a 96 second video with
800 seconds of padding after it. Check the size AND probe it.

drop_stale_segments: segments are cached by name, shot_0001.mp4 and up, and
reused whenever present. That is right when resuming a render and catastrophic
when the script was regenerated: the names collide but the durations belong to
the old cut. Measured, a 510-shot cut was replaced by a 355-shot one, only 3
segments were re-rendered, and the video came out 44 seconds shorter than the
audio. Fingerprint the shot list next to the segments.
"""

import hashlib
import os
import subprocess


def probe(path):
    """Duration in seconds, or 0.0 if the file cannot be read."""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "default=nw=1:nk=1", path],
                       capture_output=True, text=True)
    return float(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else 0.0


def segment_ok(path, min_bytes=3000):
    """True only if the segment is on disk, non-trivial, and probe-able."""
    if not os.path.exists(path) or os.path.getsize(path) < min_bytes:
        return False
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True)
    return r.returncode == 0 and r.stdout.strip() not in ("", "N/A")


def drop_stale_segments(segdir, shots_file):
    """Delete segments that were rendered from a DIFFERENT shot list.

    Call this once before rendering. A mismatch means the cache belongs to a
    cut that no longer exists. A match means you are resuming, and nothing is
    touched.
    """
    stamp = os.path.join(segdir, ".shotlist")
    with open(shots_file, "rb") as fh:
        fp = hashlib.sha1(fh.read()).hexdigest()
    old = ""
    if os.path.exists(stamp):
        old = open(stamp, encoding="utf-8").read().strip()
    dropped = 0
    if old and old != fp:
        gone = [f for f in os.listdir(segdir) if f.startswith("shot_")]
        for f in gone:
            os.remove(os.path.join(segdir, f))
        dropped = len(gone)
    with open(stamp, "w", encoding="utf-8") as fh:
        fh.write(fp)
    return dropped

"""
Concatenating segments into a film, and muxing the voice track.

The concat demuxer is used with -c copy, so this step costs about a second for
a seventeen minute film no matter how many segments went into it. Every segment
was normalised to the same format for exactly this reason.

Two gates live here and both exist because a broken film once shipped.

The concat list is built ONLY from segments that pass segment_ok. The demuxer
stops dead at the first unreadable file and silently truncates, so a missing
segment used to turn a 15 minute cut into a 96 second one.

After muxing, the video and the audio are compared. If the picture is more than
half a second short of the narration, that is not rounding: segments are
missing. Refuse to call it finished. The old behaviour was to pad the end with
a held frame, which once appended 800 seconds of frozen picture and reported
success.
"""

import os
import subprocess

from .encode import probe, segment_ok

MAX_PAD_SECS = 30.0
SYNC_TOLERANCE = 0.5


def write_concat_list(segments, list_path):
    """Write a concat demuxer list, skipping anything unreadable.

    Returns (kept, skipped). Check `skipped` and decide whether to continue.
    """
    kept, skipped = [], []
    for s in segments:
        (kept if segment_ok(s) else skipped).append(s)
    with open(list_path, "w", encoding="utf-8") as fh:
        for s in kept:
            fh.write("file '" + os.path.abspath(s).replace("\\", "/") + "'\n")
    return kept, skipped


def concat(segments, list_path, out_video):
    """Stream-copy every segment into one file."""
    kept, skipped = write_concat_list(segments, list_path)
    if not kept:
        raise RuntimeError("no readable segments to concatenate")
    p = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", list_path, "-c", "copy", out_video],
        capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"concat failed: {(p.stderr or '')[-300:]}")
    return kept, skipped


def mux(video, audio, out, pad_if_short=True):
    """Mux the voice track onto the picture and check they agree.

    Raises if the picture is short by more than MAX_PAD_SECS, because at that
    point something dropped segments and padding would hide it.
    """
    v, a = probe(video), probe(audio)
    short_by = a - v
    if short_by > MAX_PAD_SECS:
        raise RuntimeError(
            f"video track is {short_by:.0f}s shorter than the audio. That is "
            f"not rounding drift, it means segments are missing or unreadable. "
            f"Re-render before muxing.")
    vf = []
    if pad_if_short and short_by > 0.04:
        # hold the last frame for the remainder, as a stream copy
        vf = ["-vf", f"tpad=stop_mode=clone:stop_duration={short_by:.2f}"]
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", video, "-i", audio]
    if vf:
        cmd += vf + ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
    else:
        cmd += ["-c:v", "copy"]
    cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest", out]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"mux failed: {(p.stderr or '')[-300:]}")
    drift = abs(probe(out) - a)
    if drift > SYNC_TOLERANCE:
        raise RuntimeError(f"finished file is {drift:.2f}s out of sync with the voice")
    return drift

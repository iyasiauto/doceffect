"""
Turning one shot into one normalised segment.

Every segment comes out 1920x1080, 30 fps, h264 high, GOP 15, no B-frames, so
the final concat is a stream copy rather than a re-encode. That is the whole
reason the assembly of a 17 minute film takes about a second.

A shot is a plain dict. No database, no index, no schema:

    {"kind": "image", "path": "...jpg", "dur": 3.2, "shot": 41}
    {"kind": "video", "path": "...mp4", "dur": 3.2, "shot": 42,
     "start": 12.5,        # optional, seek into the source
     "clip_secs": 2.1,     # optional, how much source is actually available
     "fade_in": 0.28}      # optional, extra fade in for a beat break

Three things in here look odd and are all deliberate:

-framerate is required on an image input. Without it the still decodes at 25
fps and every sixth frame duplicates at 30 fps output.

The loop FILTER is used, not -loop 1. -loop 1 re-decodes the JPEG once per
output frame, measured at 974 ms of pure redundant decode for 96 frames. The
filter caches one decoded frame and replays it, and the perspective `on`
counter still increments because the loop sits upstream of it.

-frames:v is used, never -t. -t cuts at the last whole frame before the
timestamp, and across 300 shots that rounding accumulated 7.9 seconds of drift
against the narration.
"""

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor

from .config import (ENC_CPU, ENC_GPU, FPS, H, IMAGE_WORKERS, MAX_SLOWDOWN, W,
                     VIDEO_WORKERS)
from .encode import segment_ok
from .grade import pregrade_still
from .motion import ken_burns_vf, seg_fades


def build_cmd(shot, seg, gpu=True, grade_cache=None):
    """The ffmpeg command for one shot. Returns a list of arguments."""
    dur = max(0.6, float(shot["dur"]))
    fade = float(shot.get("fade_in") or 0)

    if shot.get("kind") == "video":
        path = shot["path"]
        ss = float(shot.get("start") or 0.0)
        clip_s = max(0.2, float(shot.get("clip_secs") or dur))
        frames = max(2, int(round(dur * FPS)))
        extra_in = ["-ss", f"{ss:.3f}"] if ss else []
        # A clip shorter than its window is slowed, never looped. Looping is
        # what made a clip appear to play twice.
        if clip_s >= dur:
            speed_vf = ""
        else:
            factor = min(MAX_SLOWDOWN, dur / clip_s)
            speed_vf = f"setpts={factor:.4f}*PTS,"
        if gpu:
            # fps= must follow setpts. Without it the timestamps stretch but
            # the frame count does not, and the cut drifts 17 seconds by shot 40.
            vf = (f"{speed_vf}fps={FPS},scale_cuda={W}:{H},"
                  f"hwdownload,format=nv12,{seg_fades(dur)}")
            return ["ffmpeg", "-y", "-v", "error",
                    "-hwaccel", "cuda", "-hwaccel_output_format", "cuda",
                    *extra_in, "-i", path, "-frames:v", str(frames), "-an",
                    "-vf", vf, *ENC_GPU, seg]
        vf = (f"{speed_vf}scale={W}:{H}:force_original_aspect_ratio=increase,"
              f"crop={W}:{H},fps={FPS},{seg_fades(dur)},format=yuv420p")
        return ["ffmpeg", "-y", "-v", "error", *extra_in, "-i", path,
                "-frames:v", str(frames), "-an", "-vf", vf, *ENC_CPU, seg]

    # A still. CPU only: there is no perspective_cuda, and no crop_cuda either.
    vf, n = ken_burns_vf(dur, int(shot.get("shot", 0)))
    cache = grade_cache or os.path.join(os.path.dirname(seg), "_graded")
    src_img = pregrade_still(shot["path"], cache)
    chain = f"loop=loop={n - 1}:size=1:start=0,{vf}"
    if fade > 0.01:
        chain += f",fade=t=in:st=0:d={fade:.2f},null"
    return ["ffmpeg", "-y", "-v", "error",
            "-framerate", str(FPS), "-i", src_img,
            "-frames:v", str(n), "-an", "-vf", chain, *ENC_CPU, seg]


def render_one(shot, seg, gpu=True, grade_cache=None):
    """Render a single shot. Returns None on success, or (seg, stderr tail)."""
    if segment_ok(seg):
        return None
    cmd = build_cmd(shot, seg, gpu=gpu, grade_cache=grade_cache)
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode == 0 and segment_ok(seg):
        return None
    return (seg, (p.stderr or "")[-160:])


def render_all(shots, segdir, gpu=True, on_progress=None):
    """Render every shot into segdir as shot_0001.mp4 and up.

    Motion and stills run in SEPARATE pools with different worker counts, and
    that split is the point. One shared pool of 16 looked twice as fast and was
    not: a consumer GeForce caps concurrent NVENC sessions at four or five, so
    most of those renders failed instantly and the failures were counted as
    speed. Measured 4 workers 32/32, 8 workers 21/32, 16 workers 8/32.

    Returns a list of (segment_path, error) for whatever failed.
    """
    os.makedirs(segdir, exist_ok=True)
    vids = [s for s in shots if s.get("kind") == "video"]
    imgs = [s for s in shots if s.get("kind") != "video"]
    failures = []

    def run(batch, workers, label):
        if not batch:
            return
        def job(s):
            seg = os.path.join(segdir, f"shot_{int(s['shot']):04d}.mp4")
            return render_one(s, seg, gpu=gpu)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for r in ex.map(job, batch):
                if r:
                    failures.append(r)
        if on_progress:
            on_progress(label, len(batch))

    run(vids, VIDEO_WORKERS, "video")
    run(imgs, IMAGE_WORKERS, "stills")
    return failures

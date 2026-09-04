"""
doceffect - the look of a faceless documentary channel, as a reusable library.

This is the effects layer lifted out of a working pipeline: the Ken Burns
movement, the colour grade, the fades, the encoder settings, the graphic card
layouts, the clip merges, and the guards that stop a broken render shipping.

It knows nothing about any particular subject, footage index or database. You
hand it a list of shots as plain dicts and it hands you back segments and a
finished film.

    from doceffect import render_all, concat, mux, GraphicCompositor

    shots = [
        {"kind": "image", "path": "a.jpg", "dur": 3.2, "shot": 1},
        {"kind": "video", "path": "b.mp4", "dur": 2.8, "shot": 2,
         "start": 4.0, "clip_secs": 6.0},
    ]
    render_all(shots, "segments/")
    concat(sorted(glob("segments/shot_*.mp4")), "list.txt", "video.mp4")
    mux("video.mp4", "voice.mp3", "final.mp4")

Start with examples/build_demo.py, and read docs/MEASUREMENTS.md before
changing any constant. Most of them look arbitrary and are not.
"""

from .assemble import concat, mux, write_concat_list
from .cards import GraphicCompositor
from .config import (ENC_CPU, ENC_GPU, FPS, H, IMAGE_WORKERS, STILL_GRADE, W,
                     VIDEO_WORKERS)
from .encode import drop_stale_segments, probe, segment_ok
from .grade import pregrade_still
from .motion import ken_burns_vf, motion_wheel, seg_fades
from .segments import build_cmd, render_all, render_one
from .transitions import crossfade, merge_pair, pick_merge_points

__version__ = "1.0.0"

__all__ = [
    "GraphicCompositor",
    "ENC_CPU", "ENC_GPU", "FPS", "H", "W", "STILL_GRADE",
    "IMAGE_WORKERS", "VIDEO_WORKERS",
    "build_cmd", "concat", "crossfade", "drop_stale_segments",
    "ken_burns_vf", "merge_pair", "motion_wheel", "mux",
    "pick_merge_points", "pregrade_still", "probe", "render_all",
    "render_one", "seg_fades", "segment_ok", "write_concat_list",
]

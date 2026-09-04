"""
Pre-grading a still, once.

The grade is identical on every frame of a Ken Burns move, so applying
colorbalance + eq + vignette inside the move ran the same arithmetic ninety
times per shot. Doing it once to the source image and caching the result took
a still shot from 2265 ms to 1483 ms.

The canvas size matters as much as the caching. Grading at 3840x2160 cost 9416
ms per still. The move only ever needs about 1.05x of the output frame, so
grading at 2032x1143 costs 787 ms for the same picture. Twelve times faster,
identical result.
"""

import os
import subprocess

from .config import KB_CANVAS_H, KB_CANVAS_W, STILL_GRADE


def pregrade_still(src, cache_dir, grade=STILL_GRADE):
    """Apply the grade to one still and return the path to the graded file.

    Returns the ORIGINAL path if ffmpeg fails, so a grading problem degrades
    the look instead of dropping the shot.
    """
    os.makedirs(cache_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(src))[0]
    out = os.path.join(cache_dir, f"{stem}_graded.jpg")
    if os.path.exists(out) and os.path.getsize(out) > 3000:
        return out
    p = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", src,
         "-vf", f"scale={KB_CANVAS_W}:{KB_CANVAS_H}:force_original_aspect_ratio=increase,"
                f"crop={KB_CANVAS_W}:{KB_CANVAS_H},{grade}",
         "-frames:v", "1", "-q:v", "2", out],
        capture_output=True, text=True)
    return out if (p.returncode == 0 and os.path.exists(out)) else src

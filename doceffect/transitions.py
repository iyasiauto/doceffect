"""
Transitions between shots: the soft dissolve, and the visible clip merge.

There are two different effects here and they are not the same thing.

crossfade is a quiet dissolve used at narration pauses. It reads as a beat
break rather than as an effect.

merge_pair is the loud one: the outgoing shot and the incoming shot visibly
overlap for about half a second. Used sparingly it is the single most
"produced" looking moment in a cut. Used often it is exhausting, so
pick_merge_points places three or four across a whole film: one inside the
fast opening, one at the centre, the rest spread.

pick_merge_points never returns adjacent indices. Two merges sharing a segment
is what used to duplicate a shot and resurrect a file that had been deleted.
"""

import subprocess

from .config import ENC_CPU


def crossfade(a_seg, b_seg, out, dur_a, xf=0.28, enc=None):
    """Dissolve b into a, writing one combined segment. Returns None on success."""
    off = max(0.0, dur_a - xf)
    fc = (f"[0:v][1:v]xfade=transition=fade:duration={xf:.2f}:offset={off:.3f},"
          f"format=yuv420p[v]")
    p = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", a_seg, "-i", b_seg,
                        "-filter_complex", fc, "-map", "[v]",
                        *(enc or ENC_CPU), out],
                       capture_output=True, text=True)
    return None if p.returncode == 0 else (out, (p.stderr or "")[-160:])


def merge_pair(a_seg, b_seg, out, dur_a, xf=0.55, enc=None):
    """The visible overlap. Same mechanism as crossfade, longer and rarer."""
    return crossfade(a_seg, b_seg, out, dur_a, xf, enc)


def pick_merge_points(rows, want, fast_secs=25.0):
    """Choose where the merges go.

    rows is any sequence of dicts carrying a "start" value in seconds.
    Returns a list of indices, never adjacent, never the first or last shot.
    """
    n = len(rows)
    if n < 6 or want < 1:
        return []
    starts = [float(r["start"]) for r in rows]
    fast_end = max((i for i, t in enumerate(starts) if t < fast_secs), default=2)
    picks = []
    if fast_end >= 3:                      # one inside the fast opening
        picks.append(max(1, fast_end // 2))
    picks.append(n // 2)                   # one at the centre
    remaining = max(0, want - len(picks))
    if remaining:
        step = n / (remaining + 1)
        for k in range(1, remaining + 1):
            picks.append(int(k * step))
    out = []
    for i in sorted(set(picks)):
        if 0 < i < n - 1 and all(abs(i - j) > 1 for j in out):
            out.append(i)
    return out[:want]

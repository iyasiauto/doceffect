"""
Ken Burns movement and the fades that top and tail every shot.

Two things here are worth knowing before you change anything.

zoompan is not used, and that is deliberate. zoompan truncates the crop origin
to whole pixels, which reads on screen as a shake: measured standard deviation
0.059 px of vertical jitter across a move. The perspective filter takes a float
rectangle and measures 0.000 px. interpolation=linear is 33% faster than cubic
and measures identically smooth, because the interpolation mode changes
sharpness, not geometry.

The fade length scales with the shot. A fixed 0.35 s in, 0.35 s out is fine on
long shots and disastrous on short ones: at a ~3 s average it put 23% of the
finished film within a hair of black. Scaling it to 5.5% of the shot, clamped
to 0.06-0.18 s, took near-black frames down to 2.7%.
"""

from .config import FPS, H, W

FADE_FRACTION = 0.055
FADE_MAX = 0.18
FADE_MIN = 0.06


def seg_fades(dur):
    """Fade in and out, scaled to the length of this particular shot."""
    f = max(FADE_MIN, min(FADE_MAX, dur * FADE_FRACTION))
    out_at = max(0.0, dur - f)
    return f"fade=t=in:st=0:d={f:.3f},fade=t=out:st={out_at:.4f}:d={f:.3f}"


def motion_wheel(static_share=0.15, buckets=24):
    """Spread the motion types evenly instead of picking each one at random.

    Random selection clusters: three zoom-ins in a row happens often enough to
    notice. A wheel guarantees the sequence that actually lands on screen is
    static, slow-zoom-in, slide-left, slow-zoom-out, slide-right, and so on.
    """
    n_s = max(0, min(buckets, round(static_share * buckets)))
    w = [None] * buckets

    def place(count, what):
        for k in range(count):
            idx = round((k + 0.5) * buckets / count) % buckets
            while w[idx]:
                idx = (idx + 1) % buckets
            w[idx] = what

    if n_s:
        place(n_s, "static")
    cycle = ["in", "slide_left", "out", "slide_right", "in", "pan"]
    j = 0
    for i in range(buckets):
        if not w[i]:
            w[i] = cycle[j % len(cycle)]
            j += 1
    return w


WHEEL = motion_wheel()


def ken_burns_vf(dur, shot_no, zoom_per_sec=0.022, wheel=None):
    """Build the filter chain for one still. Returns (filter_string, n_frames).

    The colour grade is NOT in here. It is baked into the pre-graded still by
    grade.pregrade_still so it runs once per image rather than once per frame.
    """
    wheel = wheel or WHEEL
    move = wheel[shot_no % len(wheel)]
    n = max(2, int(round(dur * FPS)))
    if move == "static":
        return (f"scale={W}:{H}:force_original_aspect_ratio=increase,"
                f"crop={W}:{H},{seg_fades(dur)},setsar=1,format=yuv420p"), n

    z = min(0.20, max(0.012, zoom_per_sec * dur))
    cw = int(round(W * (1 + z) / 16) * 16)          # must be a multiple of 16
    ch = int(round(cw * H / W))
    n1 = max(1, n - 1)

    if move in ("in", "out"):
        ax, ay = (cw - W) / 2 / n1, (ch - H) / 2 / n1
        p = "on" if move == "in" else f"({n1}-on)"
        left, top = f"{ax:.4f}*{p}", f"{ay:.4f}*{p}"
        right, bot = f"{cw}-{ax:.4f}*{p}", f"{ch}-{ay:.4f}*{p}"
    elif move in ("slide_left", "slide_right"):
        # a horizontal slide keeps the crop size fixed and moves it across
        sx, ty = (cw - W) / n1, (ch - H) / 2
        p = f"({n1}-on)" if move == "slide_right" else "on"
        left, top = f"{sx:.4f}*{p}", f"{ty:.4f}"
        right, bot = f"{sx:.4f}*{p}+{W}", f"{ty + H:.4f}"
    else:                                            # generic pan
        sx, ty = (cw - W) / n1, (ch - H) / 2
        p = f"({n1}-on)" if shot_no % 2 else "on"
        left, top = f"{sx:.4f}*{p}", f"{ty:.4f}"
        right, bot = f"{sx:.4f}*{p}+{W}", f"{ty + H:.4f}"

    persp = ("perspective=eval=frame:sense=source:interpolation=linear:"
             f"x0='{left}':y0='{top}':x1='{right}':y1='{top}':"
             f"x2='{left}':y2='{bot}':x3='{right}':y3='{bot}'")
    return (f"scale={cw}:{ch}:force_original_aspect_ratio=increase,crop={cw}:{ch},"
            f"{persp},scale={W}:{H}:flags=bicubic,{seg_fades(dur)},setsar=1,"
            f"format=yuv420p"), n

"""
Build a film from a CSV of shots and a voice track.

    python examples/build_demo.py shots.csv voice.mp3 out_dir [--cpu]

The CSV needs these columns, and nothing else is required:

    shot,kind,path,dur
    1,image,C:/pics/a.jpg,3.2
    2,video,C:/clips/b.mp4,2.8

Optional columns, used if present: start, clip_secs, fade_in.

This is deliberately short. It is the whole pipeline: render, merge, concat,
mux. Everything interesting lives in the library.
"""

import argparse
import csv
import os
import sys
from glob import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from doceffect import (concat, drop_stale_segments, merge_pair, mux, probe,  # noqa: E402
                       pick_merge_points, render_all)


def load(csv_path):
    shots = []
    start = 0.0
    for r in csv.DictReader(open(csv_path, encoding="utf-8")):
        dur = float(r["dur"])
        s = {"shot": int(r["shot"]), "kind": r.get("kind", "image"),
             "path": r["path"], "dur": dur, "start_time": start}
        for opt in ("start", "clip_secs", "fade_in"):
            if r.get(opt):
                s[opt] = float(r[opt])
        shots.append(s)
        start += dur
    return shots


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("shots")
    ap.add_argument("voice")
    ap.add_argument("out")
    ap.add_argument("--cpu", action="store_true", help="no NVENC available")
    ap.add_argument("--merges", type=int, default=3,
                    help="visible clip overlaps, 3 or 4 is plenty for a film")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    segdir = os.path.join(a.out, "segments")
    os.makedirs(segdir, exist_ok=True)

    shots = load(a.shots)
    dropped = drop_stale_segments(segdir, a.shots)
    if dropped:
        print(f"  cleared {dropped} segment(s) from a different cut")

    print(f"  rendering {len(shots)} shots")
    failures = render_all(shots, segdir, gpu=not a.cpu)
    if failures:
        print(f"  ! {len(failures)} shot(s) failed:")
        for seg, err in failures[:5]:
            print(f"      {os.path.basename(seg)}: {err}")

    segs = sorted(glob(os.path.join(segdir, "shot_*.mp4")))

    # The visible overlaps. Merging replaces two segments with one combined
    # file, so walk the picks from the END and the earlier indices stay valid.
    rows = [{"start": s["start_time"]} for s in shots]
    picks = pick_merge_points(rows, a.merges)
    for i in sorted(picks, reverse=True):
        if i + 1 >= len(segs):
            continue
        out = os.path.join(segdir, f"merge_{i:04d}.mp4")
        err = merge_pair(segs[i], segs[i + 1], out, probe(segs[i]), xf=0.55)
        if not err:
            segs[i:i + 2] = [out]
    print(f"  {len(picks)} clip merge(s) placed")

    video = os.path.join(a.out, "video_track.mp4")
    kept, skipped = concat(segs, os.path.join(a.out, "concat.txt"), video)
    if skipped:
        print(f"  ! skipped {len(skipped)} unreadable segment(s)")

    final = os.path.join(a.out, "final.mp4")
    drift = mux(video, a.voice, final)
    print(f"  -> {final}   {probe(final) / 60:.2f} min   sync {drift * 1000:.0f} ms")


if __name__ == "__main__":
    main()

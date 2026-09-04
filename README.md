# doceffect

The visual layer of a faceless documentary channel, pulled out of a working
pipeline so it can be dropped into a new niche without rebuilding any of it.

It contains the movement, the grade, the fades, the encoder settings, the
graphic card layouts, the clip merges and the assembly guards. It contains no
subject matter, no footage index and no database. You give it a list of shots;
it gives you segments and a finished film.

Built for 20 published episodes averaging 16.5 minutes. A 17 minute film
assembles from ~350 segments in about a second, because every segment is
normalised to the same format and the final concat is a stream copy.

## Install

```bash
pip install -r requirements.txt
```

You also need `ffmpeg` and `ffprobe` on PATH. For GPU encoding you need an
ffmpeg built with NVENC; pass `gpu=False` if you do not have one.

## The shot format

A shot is a plain dict. That is the whole interface.

```python
{"kind": "image", "path": "photo.jpg", "dur": 3.2, "shot": 1}

{"kind": "video", "path": "clip.mp4", "dur": 2.8, "shot": 2,
 "start": 4.0,        # optional: seek into the source
 "clip_secs": 6.0,    # optional: how much source is actually available
 "fade_in": 0.28}     # optional: longer fade in, for a beat break
```

`shot` is the index. It orders the output and it drives which Ken Burns move a
still gets, so keep it sequential.

## Minimal use

```python
from glob import glob
from doceffect import render_all, concat, mux, drop_stale_segments

drop_stale_segments("segments", "shots.csv")   # clears a cache from another cut
render_all(shots, "segments")
segs = sorted(glob("segments/shot_*.mp4"))
concat(segs, "list.txt", "video.mp4")
mux("video.mp4", "voice.mp3", "final.mp4")     # raises if they disagree
```

`examples/build_demo.py` is a runnable version that takes a CSV and a voice
track.

## What is in here

| Module | What it gives you |
|---|---|
| `config` | Frame size, fps, encoder profiles, worker counts, the colour grade |
| `motion` | Ken Burns via `perspective`, the motion wheel, shot-scaled fades |
| `grade` | Pre-grading a still once instead of once per frame |
| `segments` | One shot to one normalised segment; the two-pool renderer |
| `transitions` | The quiet dissolve, the visible clip merge, and where to put them |
| `cards` | Seven graphic card layouts, composed from your own photos |
| `assemble` | Concat, mux, and the gates that refuse a broken film |
| `encode` | `segment_ok`, the stale-segment guard, `probe` |

## Graphic cards

`GraphicCompositor` builds full-frame cards from your own photographs. Seven
layouts: a rounded card on a printed grid, a triptych, split typography with a
rule, a centred headline, a quote caption, and polaroids in portrait and
landscape. Grid backgrounds ship in `assets/grids/`.

Every position in `cards.py` is a proportion of the frame, not a pixel, so the
same layouts compose correctly at 1920x1080, at 1080x1920 for vertical, or at
any other size.

```python
from doceffect import GraphicCompositor as G
G.style1_rounded_card_on_grid("photo.jpg", "assets/grids/gen_dark_teal.jpg",
                              "card.png", 1920, 1080)
G.style4_centered_headline("photo.jpg", "THE RULE NOBODY WROTE DOWN",
                           "card.png", 1920, 1080)
```

In production these sit on screen for the length of one shot, 30 to 40 per
film, rotating through all the layouts and seeded into the first minute rather
than saved for later.

## Clip merges

The loud transition: the outgoing shot and the incoming shot visibly overlap
for about half a second. Three or four per film, never more.

```python
from doceffect import pick_merge_points, merge_pair

for i in pick_merge_points(rows, want=4):        # never adjacent indices
    merge_pair(segs[i], segs[i + 1], out, dur_of_a, xf=0.55)
```

`pick_merge_points` puts one inside the fast opening, one at the centre, and
spreads the rest. It never returns adjacent indices, because two merges sharing
a segment duplicates a shot.

## Before you change a constant

Read [docs/MEASUREMENTS.md](docs/MEASUREMENTS.md). Every number in `config.py`
came from a measurement, and several of them are counter-intuitive:

- More render workers is **slower**, and fails silently rather than loudly.
- `zoompan` shakes; `perspective` does not.
- Grading a still at 4K costs 12x what grading it at 2032x1143 costs, for the
  same picture.
- `-t` drifts; `-frames:v` does not.

## Licence

Not specified. Add one before sharing this outside your own projects.

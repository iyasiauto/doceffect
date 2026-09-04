# Why the numbers are what they are

Everything here was measured on real footage on one machine (RTX GPU, Windows,
ffmpeg with NVENC). None of it was chosen for looking round. If you change a
constant, change it because you measured something different, not because the
value looks arbitrary — most of them look arbitrary and are not.

## Encoding

| Setting | Value | Why |
|---|---|---|
| NVENC preset | `p1` | 27% faster than `p4` at the same VBR size: 148 ms vs 202 ms per clip |
| Rate control | `vbr -b:v 2500k` | Against CQ 23, a 16 minute episode went from ~886 MB to ~209 MB with no visible loss |
| GOP | `15`, `-bf 0` | Keeps every segment independently seekable, which is what lets the final concat be a stream copy |
| `-pix_fmt` | CPU only | GPU frames carry their own pixel format; setting it on the GPU path fails |

## Workers

A consumer GeForce caps concurrent NVENC sessions at about four or five. Going
wider does not fail loudly, it fails *instantly*, and the failures look like
speed.

| Workers | Renders that succeeded |
|---|---|
| 4 | 32 / 32 |
| 8 | 21 / 32 |
| 16 | 8 / 32 |

Hence two separate pools: `VIDEO_WORKERS = 8` (GPU decode, tolerant) and
`IMAGE_WORKERS = 3` (CPU-bound on the perspective filter).

## Ken Burns

`zoompan` is not used. It truncates the crop origin to whole pixels, which
reads on screen as a shake:

| Filter | Vertical jitter (sd) |
|---|---|
| `zoompan` | 0.059 px |
| `perspective` | 0.000 px |

`interpolation=linear` is 33% faster than `cubic` and measures identically
smooth, because the interpolation mode changes sharpness, not geometry.

## Pre-grading stills

The grade is identical on every frame of a move, so running it inside the move
repeats the same arithmetic ~90 times per shot.

| Approach | Cost per still |
|---|---|
| Grade every frame | 2265 ms |
| Grade once, at 3840x2160 | 9416 ms |
| Grade once, at 2032x1143 | 787 ms |

2032x1143 is used because the move never needs more than about 1.05x of the
output frame. Grading at 4K did four times the pixel work for the same picture.

## Fades

A fixed 0.35 s in / 0.35 s out is fine on long shots and wrong on short ones.
At a ~3 s average shot length it put a large share of the film within a hair of
black.

| Fade | Near-black frames |
|---|---|
| Fixed 0.35 s | 23% |
| Scaled 5.5%, clamped 0.06–0.18 s | 2.7% |

## Timing traps

Three separate causes of drift against narration, all fixed:

- `setpts` without a following `fps=` stretches timestamps but not the frame
  count. Measured +17 s of drift by shot 40.
- `-t` cuts at the last whole frame before the timestamp. Across 300 shots that
  rounding accumulated 7.9 s. Use `-frames:v`.
- An image input without `-framerate` decodes at 25 fps, so every sixth frame
  duplicates at 30 fps output.

## Image decoding

`-loop 1` re-decodes the source image once per output frame: 974 ms of pure
redundant decode for 96 frames. The `loop` **filter** caches one decoded frame
and replays it, and the `perspective` `on` counter still increments because the
loop sits upstream of it.

## Guards, and the bugs that earned them

- **`segment_ok`** — `os.path.exists()` alone let 0-byte and half-written NVENC
  outputs through. The concat demuxer stops dead at the first unreadable file
  and silently truncates: a 295-segment cut once produced a 96 second video
  followed by 800 seconds of padding, and reported success.
- **`drop_stale_segments`** — segments are cached by filename and reused. That
  is right when resuming and catastrophic when the shot list changed: a
  510-shot cut was replaced by a 355-shot one, only 3 segments re-rendered, and
  the picture came out 44 s shorter than the audio. Fingerprint the shot list.
- **`mux` refuses a large pad** — padding a short picture with a held frame
  hides missing segments. Anything over 30 s is an error, not a pad.
- **`pick_merge_points` never returns adjacent indices** — two merges sharing a
  segment duplicated a shot and resurrected a file that had been deleted.

## Things that do not exist

There is no `perspective_cuda` and no `crop_cuda`. Ken Burns on stills is CPU
only. Do not go looking for a GPU path for it.

## Things that did not help

CUDA decode plus `scale_cuda` measured dead level with CPU filters on short
clips (0.977 s vs 0.921 s for six clips). It is kept because it costs nothing
and keeps the motion path on the GPU, not because it is faster.

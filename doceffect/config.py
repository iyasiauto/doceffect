"""
Output format and encoder settings.

Every number here was measured on real footage, not chosen for looking round.
The reasoning is in docs/MEASUREMENTS.md; the short version sits beside each
value so you do not have to go and look.
"""

W, H, FPS = 1920, 1080, 30

# Ken Burns never asks for more than about 1.05x of the output frame, so the
# still pre-grade renders at this rather than at 2x or 4K. Grading a still at
# 3840x2160 did four times the pixel work for no visible gain and cost 9.4
# seconds per image instead of 0.8.
KB_CANVAS_W, KB_CANVAS_H = 2032, 1143

# A motion clip shorter than its window is slowed to fit, up to this factor.
# Past it the clip holds its last frame instead. Looping was what made a clip
# appear to play twice.
MAX_SLOWDOWN = 1.8

# The colour grade. Applied ONCE to a still before the Ken Burns move rather
# than on every frame of it: the grade is identical on all 90 frames, so
# running it per frame repeated the same arithmetic ninety times.
STILL_GRADE = (
    "colorbalance=rs=-0.07:gs=0.01:bs=0.09:rm=0.03:gm=0.0:bm=-0.02"
    ":rh=0.055:gh=0.02:bh=-0.045,"
    "eq=contrast=1.14:saturation=1.10:brightness=-0.02,"
    "vignette=PI/5"
)

# h264_nvenc preset p1, VBR 2500k.
#   p1 is 27% faster than p4 at the same VBR size (148 vs 202 ms per clip).
#   VBR 2500k against CQ 23 took a 16 minute episode from ~886 MB to ~209 MB
#   with no visible loss.
#   GOP 15 and no B-frames keep every segment independently seekable, which is
#   what lets the final concat be a stream copy instead of a re-encode.
# GPU frames carry their own pixel format, so -pix_fmt must NOT be set there.
ENC_GPU = ["-c:v", "h264_nvenc", "-preset", "p1", "-rc", "vbr",
           "-b:v", "2500k", "-maxrate", "3500k", "-bufsize", "5000k",
           "-profile:v", "high", "-g", "15", "-bf", "0"]
ENC_CPU = ENC_GPU + ["-pix_fmt", "yuv420p"]

# Worker counts, measured. These are NOT interchangeable and raising them does
# not help: a consumer GeForce caps concurrent NVENC sessions at about four to
# five. At 16 workers only 8 of 32 renders succeeded and the rest failed
# instantly; at 8 workers 21 of 32; at 4 workers 32 of 32. Video shots stream
# copy or decode on the GPU so they tolerate more; stills are CPU-bound on the
# perspective filter and do better with fewer.
VIDEO_WORKERS = 8
IMAGE_WORKERS = 3

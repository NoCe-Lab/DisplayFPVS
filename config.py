# config.py — Shared constants for the Semantic FPVS EEG task
#
# All configurable parameters are gathered here.
# fpvs_task.py imports from this file.

# ──────────────────────────────────────────────────────────────
#  CONDITIONS & STIMULUS STRUCTURE
# ──────────────────────────────────────────────────────────────
CONDITIONS = ["easy", "hard"]

# [n standard, n oddball] per cycle  →  4 standard + 1 oddball = 5 images/cycle
STIM_PATTERN = [4, 1]

# Base stimulus directory (relative to script location)
STIM_BASE_DIR = "stimuli"

# Each condition has two sub-folders:
STIM_SUBDIRS = ["standard", "odd"]

# ──────────────────────────────────────────────────────────────
#  TIMING
# ──────────────────────────────────────────────────────────────
TARGET_FREQ = 6           # Hz — target stimulation frequency
FRAME_OFF = 1             # number of blank frames between stimuli
# frame_on is computed at runtime: int(round(refresh_rate / TARGET_FREQ)) - FRAME_OFF

BLOCK_DURATION_S = 60.0   # seconds per block (1 block per run)
WAIT_DURATION_S = 2.0     # wait before block starts

# ──────────────────────────────────────────────────────────────
#  VISUAL PARAMETERS
# ──────────────────────────────────────────────────────────────
SCREEN_SIZE = [1920, 1080]
SCREEN_NUMBER = 1                    # 0 = primary, 1 = second monitor
BG_COLOR = [138, 138, 138]        # rgb255
STIM_SIZE = [6.53, 6.53]          # degrees of visual angle
SINUSOIDAL_STIM = False
FADE_IN = False
FADE_IN_CYCLES = 2.0
FADE_OUT = False
FADE_OUT_CYCLES = 2.0
RANDOMLY_VARY_SIZE = False
SIZE_PERCENT_RANGE = [74, 120]
SIZE_PERCENT_STEPS = 2

# ──────────────────────────────────────────────────────────────
#  FIXATION CROSS
# ──────────────────────────────────────────────────────────────
FIXATION_SIZE = 0.5               # degrees of visual angle (arm length)
FIXATION_COLOR = [255, 255, 255]  # rgb255 — white
FIXATION_LINE_WIDTH = 3           # pixels

# ──────────────────────────────────────────────────────────────
#  EEG TRIGGERS (parallel port)
# ──────────────────────────────────────────────────────────────
USE_TRIGGERS = True
PARALLEL_PORT_ADDRESS = 0xEFE8

TRIGGER_BLOCK_START = 100
TRIGGER_BLOCK_END = 101
TRIGGER_STANDARD = 10
TRIGGER_ODD = {
    "easy": 21,
    "hard": 22,
}

# ──────────────────────────────────────────────────────────────
#  PHOTODIODE
# ──────────────────────────────────────────────────────────────
SHOW_PHOTODIODE = True
SHOW_ODDBALL_PHOTODIODE = False
# Top-right corner (norm coords)
PHOTODIODE_SIZE = [0.08, 0.08]         # norm units
PHOTODIODE_ON_COLOR = [255, 255, 255]  # white
PHOTODIODE_OFF_COLOR = [0, 0, 0]       # black
PHOTODIODE_ON_FRAMES = 6              # ~100 ms at 60 Hz — flash on oddball onset

# ──────────────────────────────────────────────────────────────
#  OUTPUT
# ──────────────────────────────────────────────────────────────
OUTPUT_DIR = "output"

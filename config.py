# config.py — Shared constants for the Semantic FPVS EEG task
#
# All configurable parameters are gathered here so that both
# generate_lists.py and fpvs_task.py import from one place.

# ──────────────────────────────────────────────────────────────
#  CONDITIONS & STIMULUS STRUCTURE
# ──────────────────────────────────────────────────────────────
CONDITIONS = ["easy", "hard", "scramble_easy", "scramble_hard"]

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

BLOCK_DURATION_S = 60.0   # seconds per block
NUM_BLOCKS_PER_CONDITION = 4
WAIT_DURATION_S = 2.0     # inter-block wait (also pre/post)

# ──────────────────────────────────────────────────────────────
#  VISUAL PARAMETERS
# ──────────────────────────────────────────────────────────────
SCREEN_SIZE = [1920, 1080]
BG_COLOR = [138, 138, 138]        # rgb255
STIM_SIZE = [6.53, 6.53]          # degrees of visual angle
SINUSOIDAL_STIM = True
FADE_IN = True
FADE_IN_CYCLES = 2.0
FADE_OUT = True
FADE_OUT_CYCLES = 2.0
RANDOMLY_VARY_SIZE = True
SIZE_PERCENT_RANGE = [74, 120]
SIZE_PERCENT_STEPS = 2

# ──────────────────────────────────────────────────────────────
#  FIXATION TASK
# ──────────────────────────────────────────────────────────────
DO_FIXATION_TASK = True
NUM_FIX_CHANGES = 8               # per block
FIX_CHANGE_DUR_S = 0.2
MIN_SECS_BTW_FIX_CHGS = 1.2
NORMAL_FIX_COLOR = [0, 0, 0]      # rgb255 — black
DETECT_FIX_COLOR = [255, 0, 0]    # rgb255 — red
RESPOND_CHAR = "space"

# ──────────────────────────────────────────────────────────────
#  EEG TRIGGERS (parallel port)
# ──────────────────────────────────────────────────────────────
USE_TRIGGERS = True
PARALLEL_PORT_ADDRESS = 0x2FB8

TRIGGER_BLOCK_START = 100
TRIGGER_BLOCK_END = 101
TRIGGER_STANDARD = 10
TRIGGER_ODD = {
    "easy": 21,
    "hard": 22,
    "scramble_easy": 23,
    "scramble_hard": 24,
}
TRIGGER_FIX_CHANGE = 50
TRIGGER_RESPONSE = 60

# ──────────────────────────────────────────────────────────────
#  PHOTODIODE
# ──────────────────────────────────────────────────────────────
SHOW_DIODE_STIMULATOR = True
# Top-right corner (norm coords)
DIODE_POS = [1, 1]                # will be adjusted to [1 - size/2, 1 - size/2]
DIODE_SIZE = [0.08, 0.08]         # norm units
DIODE_ON_COLOR = [255, 255, 255]  # white
DIODE_OFF_COLOR = [0, 0, 0]       # black
PHOTODIODE_ON_FRAMES = 6          # ~100 ms at 60 Hz — flash on oddball onset

# ──────────────────────────────────────────────────────────────
#  OUTPUT
# ──────────────────────────────────────────────────────────────
OUTPUT_DIR = "output"

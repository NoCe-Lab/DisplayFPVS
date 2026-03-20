# Semantic FPVS EEG Task

Adapted from [DisplayFPVS](https://github.com/JosephArizpe/DisplayFPVS) (Joseph M. Arizpe, 2017) for a **Semantic FPVS** EEG paradigm with 4 conditions.

## Overview

Images are presented at 6 Hz (one every ~167 ms) in cycles of 4 standard + 1 oddball (oddball rate = 1.2 Hz). Two conditions vary the semantic distance between standard and oddball categories:

| Condition | Standard | Oddball | Images |
|-----------|----------|---------|--------|
| easy | category A | category B (far) | Original |
| hard | category A | category B (close) | Original |
| easy_scrambled | category A | category B (far) | Phase-scrambled |
| hard_scrambled | category A | category B (close) | Phase-scrambled |

The scrambled conditions use phase-scrambled versions of the same images as control baselines. The experimenter selects the condition and subject ID at startup. One block of 60 s is run per experiment. No image is repeated within a block.

Features: sinusoidal opacity modulation, fade in/out, random size jitter, EEG parallel port triggers (condition-specific oddball codes), photodiode flash (top-right) on oddball onset.

## Directory Structure

```
FPVS/
├── config.py              # All configurable parameters
├── fpvs_task.py           # Main presentation script
├── stimuli/
│   ├── easy/standard/              # Standard images for easy condition
│   ├── easy/odd/                   # Oddball images for easy condition
│   ├── hard/standard/
│   ├── hard/odd/
│   ├── easy_scrambled/standard/    # Phase-scrambled easy standard
│   ├── easy_scrambled/odd/         # Phase-scrambled easy oddball
│   ├── hard_scrambled/standard/
│   └── hard_scrambled/odd/
└── output/                # Per-subject output (gitignored)
    └── <subject_id>/
```

## Installation

Requires **Python 3.11**.

### Windows

1. Open a terminal: press `Win + R`, type `cmd`, press Enter.
2. Install Python 3.11 from [python.org](https://www.python.org/downloads/) — check **"Add Python to PATH"** during setup.
3. Navigate to the project folder (replace the path with yours):
   ```cmd
   cd C:\Users\YourName\Desktop\DeployFPVS
   ```
4. Create and activate a virtual environment, then install dependencies:
   ```cmd
   py -3.11 -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

### macOS / Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> **Note:** wxPython is a PsychoPy dependency but is not needed for this script-based experiment. If `pip install` fails building wxPython, install without it:
> ```bash
> # macOS/Linux
> pip install --no-deps psychopy==2025.2.4
> pip install -r requirements.txt --ignore-installed psychopy
> ```
> ```cmd
> :: Windows
> pip install --no-deps psychopy==2025.2.4
> pip install -r requirements.txt --ignore-installed psychopy
> ```

## Setup

### Adding stimulus images

Images must be placed under `stimuli/` following this structure:

```
stimuli/
├── easy/
│   ├── standard/    ← standard category images (e.g. tools)
│   └── odd/         ← oddball category images (e.g. animals)
├── hard/
│   ├── standard/    ← standard category images
│   └── odd/         ← oddball category images (semantically close to standard)
├── easy_scrambled/
│   ├── standard/    ← phase-scrambled versions of easy/standard/
│   └── odd/         ← phase-scrambled versions of easy/odd/
└── hard_scrambled/
    ├── standard/    ← phase-scrambled versions of hard/standard/
    └── odd/         ← phase-scrambled versions of hard/odd/
```

Each condition folder must contain enough **unique** images to cover a full 60 s block without repetition. At 6 Hz with a 4-standard + 1-oddball cycle:

- **standard/**: at least 288 images (4 per cycle × 72 cycles/min)
- **odd/**: at least 72 images (1 per cycle × 72 cycles/min)

Accepted formats: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.tif`, `.tiff`, `.gif`.

> The scrambled conditions are control baselines — use phase-scrambled versions of the exact same images as the corresponding non-scrambled condition.

### Configuration

Configure experiment parameters in `config.py` (screen resolution, parallel port address, etc.).

## Running

**Windows:**
```cmd
.venv\Scripts\activate
python fpvs_task.py
```

**macOS / Linux:**
```bash
source .venv/bin/activate
python fpvs_task.py
```

The dialog will ask for Subject ID and Condition (easy / hard / easy_scrambled / hard_scrambled).

## Output

All output is saved to `output/<subject_id>/`:

- `<subject>_<condition>_onsets.csv` — per-image onset log (filename, type, trigger code, onset time, frame number)
- `<subject>_<condition>_stim_order.csv` — full stimulus order for the run
- `<subject>_<condition>_runInfo.txt` — experimental parameters and metadata

## Trigger Scheme

| Event | Code |
|-------|------|
| Block start | 100 |
| Block end | 101 |
| Standard onset | 10 |
| Oddball easy | 21 |
| Oddball hard | 22 |
| Oddball easy_scrambled | 23 |
| Oddball hard_scrambled | 24 |

## Credits

Original SSVEP.py by Joseph M. Arizpe (Harvard Medical School, 2017). Semantic FPVS adaptation for Valentina's lab at UNIGE.

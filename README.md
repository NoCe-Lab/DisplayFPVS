# Semantic FPVS EEG Task

Adapted from [DisplayFPVS](https://github.com/JosephArizpe/DisplayFPVS) (Joseph M. Arizpe, 2017) for a **Semantic FPVS** EEG paradigm with 2 conditions.

## Overview

Images are presented at 6 Hz (one every ~167 ms) in cycles of 4 standard + 1 oddball (oddball rate = 1.2 Hz). Two conditions vary the semantic distance between standard and oddball categories:

| Condition | Standard | Oddball |
|-----------|----------|---------|
| easy | category A | category B (far) |
| hard | category A | category B (close) |

The experimenter selects the condition and subject ID at startup. One block of 60 s is run per experiment. No image is repeated within a block.

Features: sinusoidal opacity modulation, fade in/out, random size jitter, EEG parallel port triggers (condition-specific oddball codes), photodiode flash (top-right) on oddball onset.

## Directory Structure

```
FPVS/
├── config.py              # All configurable parameters
├── fpvs_task.py           # Main presentation script
├── SSVEP.py               # Original reference (Python 2, untouched)
├── stimuli/
│   ├── easy/standard/     # Standard images for easy condition
│   ├── easy/odd/          # Oddball images for easy condition
│   ├── hard/standard/
│   └── hard/odd/
└── output/                # Per-subject output (gitignored)
    └── <subject_id>/
```

## Setup

1. Install Python 3.11 and PsychoPy 2025.2.4 (`pip install psychopy==2025.2.4`).
2. Place stimulus images in the appropriate `stimuli/<condition>/<standard|odd>/` folders. You need enough unique images to fill 60 s without repetition (~288 standard + ~72 oddball at 6 Hz).
3. Configure experiment parameters in `config.py` (screen resolution, parallel port address, etc.).

## Running

```bash
python fpvs_task.py
```

The dialog will ask for Subject ID and Condition (easy / hard).

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

## Credits

Original SSVEP.py by Joseph M. Arizpe (Harvard Medical School, 2017). Semantic FPVS adaptation for Valentina's lab at UNIGE.

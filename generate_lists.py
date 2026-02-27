#!/usr/bin/env python3
"""generate_lists.py — Per-subject pseudo-random stimulus list generator.

Usage:
    python generate_lists.py --subject SUB01
    python generate_lists.py --subject SUB01 --num-blocks 4

The RNG is seeded from sha256(subject_id) so results are fully reproducible
for any given subject.  Lists are saved as CSV under  output/<subject_id>/.

Adapted from SSVEP.py Generate_stimList() (L139-180).
"""

import argparse
import csv
import hashlib
import os
import random
import math
import sys

from config import (
    CONDITIONS,
    STIM_PATTERN,
    STIM_BASE_DIR,
    STIM_SUBDIRS,
    TARGET_FREQ,
    FRAME_OFF,
    BLOCK_DURATION_S,
    NUM_BLOCKS_PER_CONDITION,
    OUTPUT_DIR,
)

# Image extensions we accept (replaces deprecated imghdr)
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".gif"}


def is_image_file(path: str) -> bool:
    """Return True if *path* looks like an image (by extension)."""
    return os.path.splitext(path)[1].lower() in IMAGE_EXTENSIONS


def seed_rng(subject_id: str) -> int:
    """Deterministic seed from subject ID via SHA-256."""
    h = hashlib.sha256(subject_id.encode()).hexdigest()
    seed = int(h, 16) % (2**31)
    random.seed(seed)
    return seed


def scan_images(directory: str) -> list[str]:
    """Return sorted list of image file paths in *directory*."""
    if not os.path.isdir(directory):
        print(f"WARNING: directory not found: {directory}")
        return []
    files = [
        f for f in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, f)) and is_image_file(f)
    ]
    files.sort()  # deterministic starting order before shuffle
    return files


def generate_condition_list(
    condition: str,
    num_blocks: int,
    stim_freq: float,
    stim_pattern: list[int],
    base_dir: str,
) -> list[dict]:
    """Generate the full stimulus sequence for one condition.

    Returns a list of dicts with keys:
        sequence, position, filename, type, full_path

    The logic mirrors SSVEP.py L159-171 — wrap-around with reshuffle,
    avoiding consecutive identical stimuli.
    """
    # Paths to the two sub-folders
    std_dir = os.path.join(base_dir, condition, STIM_SUBDIRS[0])
    odd_dir = os.path.join(base_dir, condition, STIM_SUBDIRS[1])

    std_files = scan_images(std_dir)
    odd_files = scan_images(odd_dir)

    if not std_files:
        sys.exit(f"ERROR: no images found in {std_dir}")
    if not odd_files:
        sys.exit(f"ERROR: no images found in {odd_dir}")

    # Shuffle initial order
    random.shuffle(std_files)
    random.shuffle(odd_files)

    all_stims = [
        [os.path.join(std_dir, f) for f in std_files],  # index 0 = standard
        [os.path.join(odd_dir, f) for f in odd_files],   # index 1 = oddball
    ]

    # Number of complete StimPattern cycles needed
    nb_patterns = num_blocks * int(
        math.ceil(BLOCK_DURATION_S * stim_freq / sum(stim_pattern))
    )

    stim_list: list[str] = []
    stim_types: list[str] = []
    stim_inds = [0, 0]

    for _ in range(nb_patterns):
        for stim_type_idx in range(len(stim_pattern)):
            for _ in range(stim_pattern[stim_type_idx]):
                stim_list.append(all_stims[stim_type_idx][stim_inds[stim_type_idx]])
                stim_types.append("standard" if stim_type_idx == 0 else "odd")
                stim_inds[stim_type_idx] += 1

                # Wrap-around with reshuffle (original L167-171)
                if stim_inds[stim_type_idx] >= len(all_stims[stim_type_idx]):
                    stim_inds[stim_type_idx] = 0
                    random.shuffle(all_stims[stim_type_idx])
                    # Avoid consecutive identical stimulus
                    while stim_list[-1] == all_stims[stim_type_idx][0]:
                        random.shuffle(all_stims[stim_type_idx])

    # Build output rows
    rows = []
    for i, (path, stype) in enumerate(zip(stim_list, stim_types)):
        rows.append({
            "sequence": i,
            "position": i % sum(stim_pattern),
            "filename": os.path.basename(path),
            "type": stype,
            "full_path": path,
        })
    return rows


def main():
    parser = argparse.ArgumentParser(
        description="Generate per-subject stimulus lists for the Semantic FPVS task."
    )
    parser.add_argument("--subject", required=True, help="Subject ID (e.g. SUB01)")
    parser.add_argument(
        "--num-blocks",
        type=int,
        default=NUM_BLOCKS_PER_CONDITION,
        help=f"Number of blocks per condition (default: {NUM_BLOCKS_PER_CONDITION})",
    )
    parser.add_argument(
        "--stim-dir",
        default=STIM_BASE_DIR,
        help=f"Base stimulus directory (default: {STIM_BASE_DIR})",
    )
    args = parser.parse_args()

    subject_id = args.subject
    num_blocks = args.num_blocks
    base_dir = args.stim_dir

    seed = seed_rng(subject_id)
    print(f"Subject: {subject_id}  |  RNG seed: {seed}")

    # Estimate actual stimulation frequency (assuming 60 Hz monitor)
    assumed_refresh = 60.0
    frames_per_cycle = round(assumed_refresh / TARGET_FREQ)
    stim_freq = assumed_refresh / frames_per_cycle
    print(f"Assumed stim frequency: {stim_freq:.2f} Hz  ({frames_per_cycle} frames/cycle)")

    # Output directory
    out_dir = os.path.join(OUTPUT_DIR, subject_id)
    os.makedirs(out_dir, exist_ok=True)

    for condition in CONDITIONS:
        rows = generate_condition_list(
            condition=condition,
            num_blocks=num_blocks,
            stim_freq=stim_freq,
            stim_pattern=STIM_PATTERN,
            base_dir=base_dir,
        )
        out_path = os.path.join(out_dir, f"{condition}_list.csv")
        with open(out_path, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["sequence", "position", "filename", "type", "full_path"]
            )
            writer.writeheader()
            writer.writerows(rows)
        print(f"  {condition}: {len(rows)} stimuli → {out_path}")

    print("Done.")


if __name__ == "__main__":
    main()

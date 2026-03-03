#!/usr/bin/env python3
"""fpvs_task.py — Semantic FPVS EEG task (main presentation script).

Adapted from SSVEP.py (Joseph M. Arizpe, 2017) for Python 3 / PsychoPy 2024+.
Presents 1 block of 60 s for one condition (easy or hard), chosen by the
experimenter in the startup dialog.

Features preserved from original SSVEP.py:
  - Frame-based presentation loop (OFF + ON frames)
  - Sinusoidal opacity modulation
  - Fade in / fade out per block
  - Random size variation
  - Photodiode (top-right, flashes at peak opacity each cycle)

Added / changed:
  - 2 conditions (easy / hard), selected via dialog
  - EEG parallel port triggers (condition-specific oddball codes)
  - Oddball photodiode flash on oddball onset (top-right corner, hidden by default)
  - Image preloading to prevent frame drops
  - Wrap-around with reshuffle when image pool exhausted (no consecutive repeats)
  - Per-image onset logging to CSV
  - Stimulus order saved to output
  - No fixation cross, no fixation task
  - Mouse cursor hidden (fullscreen)
  - French instructions
"""

from psychopy import visual, core, event, gui, parallel
import os
import sys
import csv
import math
import random

from config import (
    CONDITIONS,
    STIM_PATTERN,
    STIM_BASE_DIR,
    STIM_SUBDIRS,
    TARGET_FREQ,
    FRAME_OFF,
    BLOCK_DURATION_S,
    WAIT_DURATION_S,
    SCREEN_SIZE,
    BG_COLOR,
    STIM_SIZE,
    SINUSOIDAL_STIM,
    FADE_IN,
    FADE_IN_CYCLES,
    FADE_OUT,
    FADE_OUT_CYCLES,
    RANDOMLY_VARY_SIZE,
    SIZE_PERCENT_RANGE,
    SIZE_PERCENT_STEPS,
    USE_TRIGGERS,
    PARALLEL_PORT_ADDRESS,
    TRIGGER_BLOCK_START,
    TRIGGER_BLOCK_END,
    TRIGGER_STANDARD,
    TRIGGER_ODD,
    SHOW_PHOTODIODE,
    SHOW_ODDBALL_PHOTODIODE,
    PHOTODIODE_SIZE,
    PHOTODIODE_ON_COLOR,
    PHOTODIODE_OFF_COLOR,
    PHOTODIODE_ON_FRAMES,
    OUTPUT_DIR,
)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".gif"}


# ═══════════════════════════════════════════════════════════════
#  TRIGGER UTILITIES
# ═══════════════════════════════════════════════════════════════

def init_parallel_port():
    """Initialize parallel port. Returns port object or None."""
    if not USE_TRIGGERS:
        print("Triggers disabled (USE_TRIGGERS=False)")
        return None
    try:
        port = parallel.ParallelPort(address=PARALLEL_PORT_ADDRESS)
        port.setData(0)
        print(f"Parallel port initialized at {hex(PARALLEL_PORT_ADDRESS)}")
        return port
    except Exception as e:
        print(f"WARNING: Could not init parallel port: {e}")
        print("Continuing without triggers.")
        return None


def send_trigger(port, code):
    """Set trigger code on parallel port (reset happens on next frame)."""
    if port is not None:
        try:
            port.setData(int(code))
        except Exception as e:
            print(f"WARNING: trigger send failed ({code}): {e}")


def reset_trigger(port):
    """Reset parallel port to 0."""
    if port is not None:
        try:
            port.setData(0)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════

def is_image_file(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in IMAGE_EXTENSIONS


def show_text_and_wait(win, text):
    """Display centred text and wait for space / escape."""
    msg = visual.TextStim(
        win, text=text, pos=[0, 0], height=0.8, wrapWidth=26,
        color=[255, 255, 255], colorSpace="rgb255",
    )
    while True:
        msg.draw()
        win.flip()
        keys = event.getKeys(keyList=["space", "escape"])
        if "escape" in keys:
            win.close()
            core.quit()
        if "space" in keys:
            return


def scan_images(directory: str) -> list[str]:
    """Return sorted list of image filenames in *directory*."""
    if not os.path.isdir(directory):
        return []
    files = [
        f for f in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, f)) and is_image_file(f)
    ]
    files.sort()
    return files


def generate_stim_list(condition: str, stim_freq: float) -> list[dict]:
    """Generate a random stimulus sequence for one block with wrap-around.

    Images are reused cyclically (reshuffled each pass) following the
    original SSVEP.py approach.  To avoid an oddball-familiarity confound,
    the standard pool is sub-sampled so that the average number of
    presentations per image is matched across standard and oddball pools.

    Returns list of dicts with keys: position, filename, type, full_path
    """
    std_dir = os.path.join(STIM_BASE_DIR, condition, STIM_SUBDIRS[0])
    odd_dir = os.path.join(STIM_BASE_DIR, condition, STIM_SUBDIRS[1])

    std_files = scan_images(std_dir)
    odd_files = scan_images(odd_dir)

    if not std_files:
        sys.exit(f"ERROR: no images found in {std_dir}")
    if not odd_files:
        sys.exit(f"ERROR: no images found in {odd_dir}")

    # Total stimuli needed for one block
    nb_patterns = int(math.ceil(BLOCK_DURATION_S * stim_freq / sum(STIM_PATTERN)))
    n_standard_needed = nb_patterns * STIM_PATTERN[0]
    n_odd_needed = nb_patterns * STIM_PATTERN[1]

    # ── Match repetition rates across pools ──────────────────────
    # Target: each standard image seen ~ same number of times as each oddball.
    # reps_per_odd = n_odd_needed / len(odd_files)
    # desired std pool size = n_standard_needed / reps_per_odd
    #                       = n_standard_needed * len(odd_files) / n_odd_needed
    n_std_available = len(std_files)
    n_odd_available = len(odd_files)

    desired_std_pool = int(round(
        n_standard_needed * n_odd_available / n_odd_needed
    ))
    # Clamp: use at least as many as oddball pool, at most all available
    std_pool_size = max(n_odd_available, min(n_std_available, desired_std_pool))

    random.shuffle(std_files)
    std_pool = std_files[:std_pool_size]

    random.shuffle(odd_files)
    odd_pool = list(odd_files)  # use all oddball images

    reps_std = n_standard_needed / std_pool_size
    reps_odd = n_odd_needed / n_odd_available
    print(f"  Standard pool: {std_pool_size}/{n_std_available} images, "
          f"~{reps_std:.1f} presentations each")
    print(f"  Oddball pool:  {n_odd_available} images, "
          f"~{reps_odd:.1f} presentations each")

    # ── Build sequence with wrap-around (SSVEP.py L159-171) ──────
    stim_list = []
    std_idx = 0
    odd_idx = 0
    seq = 0

    for _ in range(nb_patterns):
        # Standard images
        for _ in range(STIM_PATTERN[0]):
            fname = std_pool[std_idx]
            stim_list.append({
                "sequence": seq,
                "position": seq % sum(STIM_PATTERN),
                "filename": fname,
                "type": "standard",
                "full_path": os.path.join(std_dir, fname),
            })
            std_idx += 1
            if std_idx >= len(std_pool):
                std_idx = 0
                last = std_pool[-1]
                random.shuffle(std_pool)
                # Avoid consecutive repeat across wrap boundary
                while std_pool[0] == last:
                    random.shuffle(std_pool)
            seq += 1

        # Oddball images
        for _ in range(STIM_PATTERN[1]):
            fname = odd_pool[odd_idx]
            stim_list.append({
                "sequence": seq,
                "position": seq % sum(STIM_PATTERN),
                "filename": fname,
                "type": "odd",
                "full_path": os.path.join(odd_dir, fname),
            })
            odd_idx += 1
            if odd_idx >= len(odd_pool):
                odd_idx = 0
                last = odd_pool[-1]
                random.shuffle(odd_pool)
                while odd_pool[0] == last:
                    random.shuffle(odd_pool)
            seq += 1

    return stim_list


def preload_images(win, image_paths):
    """Return dict {path: ImageStim} with all images preloaded."""
    cache = {}
    for p in image_paths:
        if p not in cache:
            cache[p] = visual.ImageStim(
                win, image=p, units="deg", size=STIM_SIZE, interpolate=True,
            )
    return cache


def compute_sin_opacity_values(frame_on):
    """Pre-compute sinusoidal opacity scaling (matching SSVEP.py L272-280)."""
    step_size = 2.0 * math.pi / (frame_on + 1.0)
    step = step_size
    vals = []
    for _ in range(frame_on):
        vals.append((math.cos(step + math.pi) + 1.0) / 2.0)
        step += step_size
    # Enforce peak = 1.0
    max_idx = vals.index(max(vals))
    vals[max_idx] = 1.0
    return vals


def generate_random_sizes(n):
    """Random size scaling factors (SSVEP.py L122-133)."""
    possible = [
        v * 0.01
        for v in range(SIZE_PERCENT_RANGE[0],
                       SIZE_PERCENT_RANGE[1] + SIZE_PERCENT_STEPS,
                       SIZE_PERCENT_STEPS)
    ]
    vals = []
    for i in range(n):
        v = random.choice(possible)
        while i > 0 and v == vals[-1]:
            v = random.choice(possible)
        vals.append(v)
    return vals


# ═══════════════════════════════════════════════════════════════
#  PARTICIPANT DIALOG
# ═══════════════════════════════════════════════════════════════

def participant_dialog():
    """Show dialog, return dict with subject_id and condition."""
    dlg = gui.Dlg(title="FPVS Sémantique")
    dlg.addText("Informations participant")
    dlg.addField("Participant :", "SUB01")
    dlg.addField("Condition :", choices=CONDITIONS)
    dlg.show()
    if not dlg.OK:
        core.quit()
    data = dlg.data
    return {"subject_id": data[0], "condition": data[1]}


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    # ── Participant info ──────────────────────────────────────
    info = participant_dialog()
    subject_id = info["subject_id"]
    condition = info["condition"]
    out_dir = os.path.join(OUTPUT_DIR, subject_id)
    os.makedirs(out_dir, exist_ok=True)

    # ── Window (not fullscreen yet, so dialog works) ──────────
    win = visual.Window(
        size=SCREEN_SIZE, color=BG_COLOR, colorSpace="rgb255",
        fullscr=False, monitor="testMonitor", units="deg",
    )

    # ── Refresh rate validation ───────────────────────────────
    frame_rate = win.getActualFrameRate(
        nIdentical=20, nMaxFrames=100, nWarmUpFrames=20, threshold=1,
    )
    if frame_rate is None:
        show_text_and_wait(
            win,
            "ERREUR : impossible de mesurer le taux\n"
            "de rafraîchissement de l'écran.\n\n"
            "Vérifiez les paramètres du moniteur.\n"
            "Appuyez sur ESPACE pour quitter.",
        )
        win.close()
        core.quit()

    print(f"Detected refresh rate: {frame_rate:.2f} Hz")

    frames_per_cycle = int(round(frame_rate / TARGET_FREQ))
    actual_freq = frame_rate / frames_per_cycle
    frame_on = frames_per_cycle - FRAME_OFF
    print(f"Actual stimulation frequency: {actual_freq:.2f} Hz")
    print(f"Frames per cycle: {frames_per_cycle}  (OFF={FRAME_OFF}, ON={frame_on})")

    if abs(actual_freq - TARGET_FREQ) > 0.5:
        print(f"WARNING: actual freq {actual_freq:.2f} differs from target {TARGET_FREQ}")

    # ── Go fullscreen + hide cursor ──────────────────────────
    win.fullscr = True
    win.winHandle.set_fullscreen(True)
    win.mouseVisible = False
    win.flip()

    # ── Generate stimulus list (wrap-around, matched repetition) ─
    print(f"Condition: {condition}")
    stim_rows = generate_stim_list(condition, actual_freq)
    total_stims = len(stim_rows)
    print(f"Stimulus sequence: {total_stims} images")

    # Save stimulus order to output
    order_path = os.path.join(out_dir, f"{subject_id}_{condition}_stim_order.csv")
    with open(order_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["sequence", "position", "filename", "type", "full_path"],
        )
        writer.writeheader()
        writer.writerows(stim_rows)
    print(f"Stimulus order saved to: {order_path}")

    # ── Preload images ────────────────────────────────────────
    unique_paths = list({r["full_path"] for r in stim_rows})
    print(f"Preloading {len(unique_paths)} images...")
    img_cache = preload_images(win, unique_paths)

    # ── Visual stimuli ────────────────────────────────────────
    image_stim = visual.ImageStim(
        win, name="image", units="deg", pos=[0, 0], size=STIM_SIZE,
        opacity=1, interpolate=True,
    )
    # Photodiode — top-right, flashes at peak opacity each cycle
    photodiode = visual.GratingStim(
        win, name="photodiode", units="norm", tex=None,
        pos=[1 - PHOTODIODE_SIZE[0] / 2, 1 - PHOTODIODE_SIZE[1] / 2],
        size=PHOTODIODE_SIZE,
        color=PHOTODIODE_OFF_COLOR, colorSpace="rgb255",
        opacity=1, interpolate=True,
    )
    # Oddball photodiode — top-right, flashes on oddball onset (hidden by default)
    oddball_photodiode = visual.GratingStim(
        win, name="oddballPhotodiode", units="norm", tex=None,
        pos=[1 - PHOTODIODE_SIZE[0] / 2, 1 - PHOTODIODE_SIZE[1] / 2],
        size=PHOTODIODE_SIZE,
        color=PHOTODIODE_OFF_COLOR, colorSpace="rgb255",
        opacity=1, interpolate=True,
    )

    # ── Parallel port ─────────────────────────────────────────
    port = init_parallel_port()

    # ── Sinusoidal opacity ────────────────────────────────────
    sin_vals = compute_sin_opacity_values(frame_on) if SINUSOIDAL_STIM else None

    # ── Random sizes ──────────────────────────────────────────
    if RANDOMLY_VARY_SIZE:
        rand_sizes = generate_random_sizes(total_stims)
    else:
        rand_sizes = [1.0] * total_stims

    # ── Onset log ─────────────────────────────────────────────
    onset_log: list[dict] = []

    # ── Clocks ────────────────────────────────────────────────
    trial_clock = core.Clock()
    wait_clock = core.Clock()
    global_clock = core.Clock()

    # ── Fade-out duration ─────────────────────────────────────
    fade_out_dur = FADE_OUT_CYCLES * sum(STIM_PATTERN) / actual_freq

    # ── Trigger code for oddballs in this condition ───────────
    oddball_trigger = TRIGGER_ODD.get(condition, TRIGGER_STANDARD)

    # ── French instructions ───────────────────────────────────
    show_text_and_wait(
        win,
        "Bienvenue !\n\n"
        "Regardez le centre de l'écran.\n\n"
        "Appuyez sur ESPACE pour commencer.",
    )

    # ── Pre-block wait ────────────────────────────────────────
    win.flip()  # blank screen
    wait_clock.reset()
    while wait_clock.getTime() < WAIT_DURATION_S:
        if event.getKeys(keyList=["escape"]):
            win.close()
            core.quit()

    # ── Block start trigger ───────────────────────────────────
    photodiode.setAutoDraw(SHOW_PHOTODIODE)
    send_trigger(port, TRIGGER_BLOCK_START)
    trial_clock.reset()
    global_clock.reset()
    frame_count = 0
    stim_num = 0
    oddball_photodiode_frames_left = 0
    stim_peak_opacity = 0.0

    # ══════════════════════════════════════════════════════════
    #  FRAME LOOP  (one iteration = one stimulus cycle)
    # ══════════════════════════════════════════════════════════
    while trial_clock.getTime() < BLOCK_DURATION_S:

        # ── OFF frames (blank, no image) ──────────────────────
        photodiode_shown = False
        photodiode.color = PHOTODIODE_OFF_COLOR

        for fn in range(FRAME_OFF):
            # Oddball photodiode management
            if oddball_photodiode_frames_left > 0:
                oddball_photodiode.color = PHOTODIODE_ON_COLOR
                oddball_photodiode_frames_left -= 1
            else:
                oddball_photodiode.color = PHOTODIODE_OFF_COLOR
            if SHOW_ODDBALL_PHOTODIODE:
                oddball_photodiode.draw()

            win.flip()
            reset_trigger(port)

            if event.getKeys(keyList=["escape"]):
                win.close()
                core.quit()
            frame_count += 1

        # ── Prepare next stimulus ─────────────────────────────
        if stim_num >= total_stims:
            print("WARNING: frame loop ran longer than expected — "
                  "ran out of pre-generated stimuli (refresh rate unstable?)")
            break

        row = stim_rows[stim_num]
        stim_path = row["full_path"]
        stim_type = row["type"]
        is_oddball = stim_type == "odd"

        # Use preloaded image
        image_stim.image = img_cache[stim_path].image
        if RANDOMLY_VARY_SIZE:
            s = rand_sizes[stim_num]
            image_stim.size = [STIM_SIZE[0] * s, STIM_SIZE[1] * s]
        else:
            image_stim.size = STIM_SIZE

        # ── Fade in / out opacity ─────────────────────────────
        if FADE_IN and stim_num == 0:
            stim_peak_opacity = 0.0
        if FADE_IN and stim_num < sum(STIM_PATTERN) * FADE_IN_CYCLES:
            stim_peak_opacity += 1.0 / (sum(STIM_PATTERN) * FADE_IN_CYCLES)
        elif FADE_OUT and fade_out_dur >= (BLOCK_DURATION_S - trial_clock.getTime()):
            stim_peak_opacity -= 1.0 / (sum(STIM_PATTERN) * FADE_OUT_CYCLES)
        else:
            stim_peak_opacity = 1.0
        stim_peak_opacity = max(0.0, min(1.0, stim_peak_opacity))

        # Trigger code for this stimulus
        trigger_code = oddball_trigger if is_oddball else TRIGGER_STANDARD

        stim_num += 1

        # Non-sinusoidal: set opacity once
        if not SINUSOIDAL_STIM:
            image_stim.opacity = stim_peak_opacity

        # ── ON frames (image displayed) ───────────────────────
        for fn in range(frame_on):
            # Sinusoidal opacity
            if SINUSOIDAL_STIM:
                image_stim.opacity = stim_peak_opacity * sin_vals[fn]

            # Photodiode (top-right) — flash at peak opacity
            if SHOW_PHOTODIODE:
                if not photodiode_shown and image_stim.opacity == stim_peak_opacity:
                    photodiode.color = PHOTODIODE_ON_COLOR
                    photodiode_shown = True
                else:
                    photodiode.color = PHOTODIODE_OFF_COLOR

            # First ON frame = onset → trigger + oddball photodiode + log
            if fn == 0:
                send_trigger(port, trigger_code)
                if is_oddball:
                    oddball_photodiode_frames_left = PHOTODIODE_ON_FRAMES
                onset_time = global_clock.getTime()
                onset_log.append({
                    "participant_id": subject_id,
                    "condition": condition,
                    "sequence": int(row["sequence"]),
                    "position": int(row["position"]),
                    "filename": row["filename"],
                    "type": stim_type,
                    "trigger_code": trigger_code,
                    "onset_time_s": f"{onset_time:.6f}",
                    "onset_frame": frame_count,
                })

            # Oddball photodiode management
            if oddball_photodiode_frames_left > 0:
                oddball_photodiode.color = PHOTODIODE_ON_COLOR
                oddball_photodiode_frames_left -= 1
            else:
                oddball_photodiode.color = PHOTODIODE_OFF_COLOR
            if SHOW_ODDBALL_PHOTODIODE:
                oddball_photodiode.draw()

            image_stim.draw()
            win.flip()

            # Reset trigger on the frame after it was set
            if fn == 1:
                reset_trigger(port)

            if event.getKeys(keyList=["escape"]):
                win.close()
                core.quit()
            frame_count += 1

    # ── Block end ─────────────────────────────────────────────
    send_trigger(port, TRIGGER_BLOCK_END)
    core.wait(0.01)
    reset_trigger(port)
    photodiode.setAutoDraw(False)

    print(f"Block done — last frame: {frame_count}, stimuli shown: {stim_num}")

    # ── Save onset log ────────────────────────────────────────
    onset_path = os.path.join(out_dir, f"{subject_id}_{condition}_onsets.csv")
    if onset_log:
        fieldnames = list(onset_log[0].keys())
        with open(onset_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(onset_log)
    print(f"Onset data saved to: {onset_path}")

    # ── Save run info ─────────────────────────────────────────
    info_path = os.path.join(out_dir, f"{subject_id}_{condition}_runInfo.txt")
    lines = [
        f"Subject ID: {subject_id}",
        f"Condition: {condition}",
        f"Detected refresh rate (Hz): {frame_rate:.2f}",
        f"Actual stimulation frequency (Hz): {actual_freq:.2f}",
        f"Target frequency (Hz): {TARGET_FREQ}",
        f"Frames per cycle: {frames_per_cycle}",
        f"Frames ON: {frame_on}",
        f"Frames OFF: {FRAME_OFF}",
        f"Block duration (s): {BLOCK_DURATION_S}",
        f"Stim pattern: {STIM_PATTERN}",
        f"Sinusoidal stim: {SINUSOIDAL_STIM}",
        f"Fade in: {FADE_IN} ({FADE_IN_CYCLES} cycles)",
        f"Fade out: {FADE_OUT} ({FADE_OUT_CYCLES} cycles)",
        f"Random size variation: {RANDOMLY_VARY_SIZE}",
        f"Size range (%): {SIZE_PERCENT_RANGE}",
        f"Triggers enabled: {USE_TRIGGERS}",
        f"Total stimuli shown: {stim_num}",
        f"Total frames: {frame_count}",
    ]
    with open(info_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Run info saved to: {info_path}")

    # ── End screen ────────────────────────────────────────────
    show_text_and_wait(
        win,
        "L'expérience est terminée.\n\n"
        "Merci pour votre participation !\n\n"
        "Appuyez sur ESPACE pour quitter.",
    )

    win.close()
    core.quit()


if __name__ == "__main__":
    main()

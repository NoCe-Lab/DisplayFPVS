#!/usr/bin/env python3
"""fpvs_task.py — Semantic FPVS EEG task (main presentation script).

Adapted from SSVEP.py (Joseph M. Arizpe, 2017) for Python 3 / PsychoPy 2024+.
Presents 4 conditions (easy / hard / scramble_easy / scramble_hard),
each with NUM_BLOCKS_PER_CONDITION blocks of BLOCK_DURATION_S seconds.

Features preserved from original SSVEP.py:
  - Frame-based presentation loop (OFF + ON frames)
  - Sinusoidal opacity modulation
  - Fade in / fade out per block
  - Random size variation
  - Fixation colour-change task with response detection & RT logging
  - Diode stimulator (bottom-left, per original) + photodiode (top-right, for EEG)

Added:
  - 4 conditions with condition-specific EEG triggers (parallel port)
  - Photodiode flash on oddball onset (top-right corner)
  - Image preloading per condition
  - Per-image onset logging to CSV
  - French instructions & inter-block breaks
  - Subject-specific output directory
  - Refresh-rate validation at startup
"""

from psychopy import visual, core, event, gui, logging, parallel
import os
import sys
import csv
import math
import random
import hashlib

from config import (
    CONDITIONS,
    STIM_PATTERN,
    STIM_BASE_DIR,
    STIM_SUBDIRS,
    TARGET_FREQ,
    FRAME_OFF,
    BLOCK_DURATION_S,
    NUM_BLOCKS_PER_CONDITION,
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
    DO_FIXATION_TASK,
    NUM_FIX_CHANGES,
    FIX_CHANGE_DUR_S,
    MIN_SECS_BTW_FIX_CHGS,
    NORMAL_FIX_COLOR,
    DETECT_FIX_COLOR,
    RESPOND_CHAR,
    USE_TRIGGERS,
    PARALLEL_PORT_ADDRESS,
    TRIGGER_BLOCK_START,
    TRIGGER_BLOCK_END,
    TRIGGER_STANDARD,
    TRIGGER_ODD,
    TRIGGER_FIX_CHANGE,
    TRIGGER_RESPONSE,
    SHOW_DIODE_STIMULATOR,
    DIODE_SIZE,
    DIODE_ON_COLOR,
    DIODE_OFF_COLOR,
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


def check_escape():
    """Return True if escape was pressed."""
    keys = event.getKeys(keyList=["escape"])
    return bool(keys)


def show_text_and_wait(win, text, fixation=None):
    """Display centred text and wait for space / escape."""
    msg = visual.TextStim(
        win, text=text, pos=[0, 0], height=0.8, wrapWidth=26,
        color=[255, 255, 255], colorSpace="rgb255",
    )
    while True:
        msg.draw()
        if fixation is not None:
            fixation.draw()
        win.flip()
        keys = event.getKeys(keyList=["space", "escape"])
        if "escape" in keys:
            win.close()
            core.quit()
        if "space" in keys:
            return


def preload_images(win, image_paths):
    """Return dict {path: ImageStim} with all images preloaded."""
    cache = {}
    for p in image_paths:
        if p not in cache:
            cache[p] = visual.ImageStim(
                win, image=p, units="deg", size=STIM_SIZE, interpolate=True,
            )
    return cache


def load_stim_list(csv_path):
    """Load a stimulus list CSV (from generate_lists.py). Returns list of dicts."""
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


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


def generate_fix_change_frames(num_changes, total_frames, num_frames_change,
                               min_frames_between):
    """Pre-compute fixation colour-change onset frames (SSVEP.py L99-117)."""
    frames = []
    max_tries = 1000
    for i in range(num_changes):
        lo = num_frames_change
        hi = total_frames - num_frames_change - min_frames_between
        if hi <= lo:
            print("WARNING: not enough room for all fixation changes")
            break
        candidate = random.randint(lo, hi)
        if i > 0:
            tries = 0
            while not all(abs(x - candidate) > min_frames_between for x in frames):
                candidate = random.randint(lo, hi)
                tries += 1
                if tries >= max_tries:
                    print("ERROR: too many fixation events / too wide spacing.")
                    sys.exit(1)
        frames.append(candidate)
    frames.sort()
    return frames


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
    """Show dialog, return dict with keys: subject_id, session."""
    dlg = gui.Dlg(title="FPVS Sémantique")
    dlg.addText("Informations participant")
    dlg.addField("Participant :", "SUB01")
    dlg.addField("Session :", "1")
    dlg.show()
    if not dlg.OK:
        core.quit()
    data = dlg.data
    return {"subject_id": data[0], "session": data[1]}


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    # ── Participant info ──────────────────────────────────────
    info = participant_dialog()
    subject_id = info["subject_id"]
    session = info["session"]
    out_dir = os.path.join(OUTPUT_DIR, subject_id)
    os.makedirs(out_dir, exist_ok=True)

    # ── Window ────────────────────────────────────────────────
    win = visual.Window(
        size=SCREEN_SIZE, color=BG_COLOR, colorSpace="rgb255",
        fullscr=False, monitor="testMonitor", units="deg",
    )

    # ── Refresh rate validation ───────────────────────────────
    frame_rate = win.getActualFrameRate(nIdentical=20, nMaxFrames=100,
                                        nWarmUpFrames=20, threshold=1)
    if frame_rate is None:
        print("WARNING: could not measure frame rate — assuming 60 Hz")
        frame_rate = 60.0
    print(f"Detected refresh rate: {frame_rate:.2f} Hz")

    frames_per_cycle = int(round(frame_rate / TARGET_FREQ))
    actual_freq = frame_rate / frames_per_cycle
    frame_on = frames_per_cycle - FRAME_OFF
    print(f"Actual stimulation frequency: {actual_freq:.2f} Hz")
    print(f"Frames per cycle: {frames_per_cycle}  (OFF={FRAME_OFF}, ON={frame_on})")

    if abs(actual_freq - TARGET_FREQ) > 0.5:
        print(f"WARNING: actual freq {actual_freq:.2f} differs from target {TARGET_FREQ}")

    # ── Go fullscreen ─────────────────────────────────────────
    win.fullscr = True
    win.winHandle.set_fullscreen(True)
    win.flip()

    # ── Visual stimuli ────────────────────────────────────────
    image_stim = visual.ImageStim(
        win, name="image", units="deg", pos=[0, 0], size=STIM_SIZE,
        opacity=1, interpolate=True,
    )
    fixation = visual.TextStim(
        win, text="+", name="fixation", units="deg", height=0.5,
        pos=[0, 0], color=NORMAL_FIX_COLOR, colorSpace="rgb255",
    )
    # Diode stimulator — bottom-left (per original)
    diode_stimulator = visual.GratingStim(
        win, name="diodeStim", units="norm", tex=None,
        pos=[-1, -1], size=[0.1, 0.1],
        color=DIODE_OFF_COLOR, colorSpace="rgb255",
        opacity=1, interpolate=True,
    )
    # Photodiode — top-right (for EEG)
    photodiode = visual.GratingStim(
        win, name="photodiode", units="norm", tex=None,
        pos=[1 - DIODE_SIZE[0] / 2, 1 - DIODE_SIZE[1] / 2],
        size=DIODE_SIZE,
        color=DIODE_OFF_COLOR, colorSpace="rgb255",
        opacity=1, interpolate=True,
    )

    # ── Parallel port ─────────────────────────────────────────
    port = init_parallel_port()

    # ── Sinusoidal opacity ────────────────────────────────────
    sin_vals = compute_sin_opacity_values(frame_on) if SINUSOIDAL_STIM else None
    if sin_vals:
        print(f"Sinusoidal opacity values: {sin_vals}")

    # ── Condition order (seeded by subject) ───────────────────
    seed_int = int(hashlib.sha256(subject_id.encode()).hexdigest(), 16) % (2**31)
    rng_order = random.Random(seed_int)
    condition_order = CONDITIONS[:]
    rng_order.shuffle(condition_order)
    print(f"Condition order: {condition_order}")

    # ── Per-image onset log ───────────────────────────────────
    onset_log: list[dict] = []
    fixation_log: list[dict] = []

    # ── Clocks ────────────────────────────────────────────────
    trial_clock = core.Clock()
    wait_clock = core.Clock()
    global_clock = core.Clock()

    # ── French instructions ───────────────────────────────────
    show_text_and_wait(
        win,
        "Bienvenue !\n\n"
        "Fixez la croix au centre de l'écran.\n"
        "Appuyez sur ESPACE dès que la croix\n"
        "change de couleur.\n\n"
        "Appuyez sur ESPACE pour commencer.",
    )

    # ══════════════════════════════════════════════════════════
    #  CONDITION LOOP
    # ══════════════════════════════════════════════════════════
    for cond_idx, condition in enumerate(condition_order):
        # ── Load stimulus list ────────────────────────────────
        list_path = os.path.join(out_dir, f"{condition}_list.csv")
        if not os.path.isfile(list_path):
            show_text_and_wait(
                win,
                f"ERREUR : liste introuvable\n{list_path}\n\n"
                "Lancez d'abord generate_lists.py\n"
                "Appuyez sur ESPACE pour quitter.",
            )
            win.close()
            core.quit()

        stim_rows = load_stim_list(list_path)
        total_stims = len(stim_rows)
        print(f"\n── Condition: {condition}  ({total_stims} stimuli) ──")

        # ── Preload images ────────────────────────────────────
        unique_paths = list({r["full_path"] for r in stim_rows})
        print(f"   Preloading {len(unique_paths)} unique images...")
        img_cache = preload_images(win, unique_paths)

        # ── Random sizes ──────────────────────────────────────
        if RANDOMLY_VARY_SIZE:
            rand_sizes = generate_random_sizes(total_stims)
        else:
            rand_sizes = [1.0] * total_stims

        # ── Stim index tracking across blocks ─────────────────
        stim_num = 0  # global index into stim_rows for this condition
        stims_per_block = int(math.ceil(
            BLOCK_DURATION_S * actual_freq / sum(STIM_PATTERN)
        )) * sum(STIM_PATTERN)

        # ── Compute total frames per block for fixation task ──
        total_frames_per_block = stims_per_block * frames_per_cycle
        frames_per_sec = actual_freq * frames_per_cycle
        num_frames_fix_change = int(round(frames_per_sec * FIX_CHANGE_DUR_S))
        min_frames_btw_fix = int(math.ceil(frames_per_sec * MIN_SECS_BTW_FIX_CHGS))

        # ── Fade-out duration ─────────────────────────────────
        fade_out_dur = FADE_OUT_CYCLES * sum(STIM_PATTERN) / actual_freq

        # ── BLOCK LOOP ────────────────────────────────────────
        for block_idx in range(NUM_BLOCKS_PER_CONDITION):
            block_label = f"{condition} bloc {block_idx + 1}/{NUM_BLOCKS_PER_CONDITION}"
            print(f"   Starting {block_label}")

            # Inter-block instruction
            if block_idx == 0:
                show_text_and_wait(
                    win,
                    f"Condition {cond_idx + 1}/{len(condition_order)}\n\n"
                    f"Bloc {block_idx + 1}/{NUM_BLOCKS_PER_CONDITION}\n\n"
                    "Fixez la croix centrale.\n"
                    "Appuyez sur ESPACE pour commencer.",
                )
            else:
                show_text_and_wait(
                    win,
                    f"Pause\n\n"
                    f"Bloc {block_idx + 1}/{NUM_BLOCKS_PER_CONDITION}\n\n"
                    "Appuyez sur ESPACE quand vous êtes prêt(e).",
                )

            # ── Fixation task setup for this block ────────────
            first_stim_of_block = stim_num
            if DO_FIXATION_TASK:
                fix_chg_frames = generate_fix_change_frames(
                    NUM_FIX_CHANGES, total_frames_per_block,
                    num_frames_fix_change, min_frames_btw_fix,
                )
                fix_chg_back_frames = [f + num_frames_fix_change for f in fix_chg_frames]
                fix_chgs_detected = [False] * len(fix_chg_frames)
                fix_chg_times = [0.0] * len(fix_chg_frames)
                response_times = [0.0] * len(fix_chg_frames)
                response_frame_nums = [0] * len(fix_chg_frames)
                fix_change_idx = 0
                fix_has_changed = False
                time_of_last_fix_change = 0.0

            # ── Pre-block wait ────────────────────────────────
            fixation.color = NORMAL_FIX_COLOR
            fixation.draw()
            win.flip()
            wait_clock.reset()
            while wait_clock.getTime() < WAIT_DURATION_S:
                if check_escape():
                    win.close()
                    core.quit()

            # ── Diode stimulator auto-draw ────────────────────
            diode_stimulator.setAutoDraw(SHOW_DIODE_STIMULATOR)

            # ── Block start trigger ───────────────────────────
            send_trigger(port, TRIGGER_BLOCK_START)
            trial_clock.reset()
            frame_count = 0
            photodiode_frames_left = 0
            stimulus_number_error = False

            # ══════════════════════════════════════════════════
            #  FRAME LOOP  (one iteration = one stimulus cycle)
            # ══════════════════════════════════════════════════
            while trial_clock.getTime() < BLOCK_DURATION_S:

                # ── OFF frames (fixation only) ────────────────
                diode_shown = False
                diode_stimulator.color = DIODE_OFF_COLOR

                for fn in range(FRAME_OFF):
                    # Fixation task check
                    if DO_FIXATION_TASK and fix_change_idx < len(fix_chg_frames):
                        if fix_chg_frames[fix_change_idx] == frame_count:
                            fixation.color = DETECT_FIX_COLOR
                            time_of_last_fix_change = trial_clock.getTime()
                            fix_chg_times[fix_change_idx] = time_of_last_fix_change
                            fix_has_changed = True
                            send_trigger(port, TRIGGER_FIX_CHANGE)
                            event.clearEvents()
                        elif fix_chg_back_frames[fix_change_idx] == frame_count:
                            fixation.color = NORMAL_FIX_COLOR
                            fix_change_idx += 1

                    # Photodiode management
                    if photodiode_frames_left > 0:
                        photodiode.color = DIODE_ON_COLOR
                        photodiode_frames_left -= 1
                    else:
                        photodiode.color = DIODE_OFF_COLOR
                    photodiode.draw()

                    fixation.draw()
                    win.flip()

                    # Reset trigger on the frame after it was sent
                    reset_trigger(port)

                    # Response check
                    keys = event.getKeys(keyList=[RESPOND_CHAR, "escape"])
                    for k in keys:
                        if k == "escape":
                            win.close()
                            core.quit()
                        if k == RESPOND_CHAR and DO_FIXATION_TASK:
                            send_trigger(port, TRIGGER_RESPONSE)
                            if (fix_change_idx > 0 and fix_has_changed
                                    and not fix_chgs_detected[fix_change_idx - 1]):
                                rt = trial_clock.getTime() - time_of_last_fix_change
                                response_times[fix_change_idx - 1] = rt
                                response_frame_nums[fix_change_idx - 1] = frame_count
                                fix_chgs_detected[fix_change_idx - 1] = True

                    frame_count += 1

                # ── Prepare next stimulus ─────────────────────
                if stim_num >= total_stims:
                    print("ERROR: more stimuli needed than prepared (refresh rate unstable?)")
                    stimulus_number_error = True
                    break

                row = stim_rows[stim_num]
                stim_path = row["full_path"]
                stim_type = row["type"]
                is_oddball = stim_type == "odd"

                # Use cached ImageStim
                cached_img = img_cache[stim_path]
                image_stim.image = cached_img.image
                if RANDOMLY_VARY_SIZE:
                    s = rand_sizes[stim_num]
                    image_stim.size = [STIM_SIZE[0] * s, STIM_SIZE[1] * s]
                else:
                    image_stim.size = STIM_SIZE

                # ── Fade in / out opacity ─────────────────────
                stims_since_block_start = stim_num - first_stim_of_block
                if FADE_IN and stim_num == first_stim_of_block:
                    stim_peak_opacity = 0.0
                if FADE_IN and stims_since_block_start < sum(STIM_PATTERN) * FADE_IN_CYCLES:
                    stim_peak_opacity = stim_peak_opacity + 1.0 / (sum(STIM_PATTERN) * FADE_IN_CYCLES)
                elif FADE_OUT and fade_out_dur >= (BLOCK_DURATION_S - trial_clock.getTime()):
                    stim_peak_opacity = stim_peak_opacity - 1.0 / (sum(STIM_PATTERN) * FADE_OUT_CYCLES)
                else:
                    stim_peak_opacity = 1.0

                stim_peak_opacity = max(0.0, min(1.0, stim_peak_opacity))

                # Trigger code for this stimulus
                if is_oddball:
                    trigger_code = TRIGGER_ODD.get(condition, TRIGGER_STANDARD)
                else:
                    trigger_code = TRIGGER_STANDARD

                stim_num += 1

                # Non-sinusoidal: set opacity once
                if not SINUSOIDAL_STIM:
                    image_stim.opacity = stim_peak_opacity

                # ── ON frames (image + fixation) ──────────────
                for fn in range(frame_on):
                    # Sinusoidal opacity
                    if SINUSOIDAL_STIM:
                        image_stim.opacity = stim_peak_opacity * sin_vals[fn]

                    # Diode stimulator (bottom-left) — flash at peak
                    if SHOW_DIODE_STIMULATOR:
                        if not diode_shown and image_stim.opacity == stim_peak_opacity:
                            diode_stimulator.color = DIODE_ON_COLOR
                            diode_shown = True
                        else:
                            diode_stimulator.color = DIODE_OFF_COLOR

                    # Fixation task check
                    if DO_FIXATION_TASK and fix_change_idx < len(fix_chg_frames):
                        if fix_chg_frames[fix_change_idx] == frame_count:
                            fixation.color = DETECT_FIX_COLOR
                            time_of_last_fix_change = trial_clock.getTime()
                            fix_chg_times[fix_change_idx] = time_of_last_fix_change
                            fix_has_changed = True
                            send_trigger(port, TRIGGER_FIX_CHANGE)
                            event.clearEvents()
                        elif fix_chg_back_frames[fix_change_idx] == frame_count:
                            fixation.color = NORMAL_FIX_COLOR
                            fix_change_idx += 1

                    # First ON frame = onset → trigger + photodiode + log
                    if fn == 0:
                        send_trigger(port, trigger_code)
                        if is_oddball:
                            photodiode_frames_left = PHOTODIODE_ON_FRAMES
                        onset_time = global_clock.getTime()
                        onset_log.append({
                            "participant_id": subject_id,
                            "session": session,
                            "condition": condition,
                            "block": block_idx + 1,
                            "sequence": int(row["sequence"]),
                            "position": int(row["position"]),
                            "filename": row["filename"],
                            "type": stim_type,
                            "trigger_code": trigger_code,
                            "onset_time_s": f"{onset_time:.6f}",
                            "onset_frame": frame_count,
                        })

                    # Photodiode management
                    if photodiode_frames_left > 0:
                        photodiode.color = DIODE_ON_COLOR
                        photodiode_frames_left -= 1
                    else:
                        photodiode.color = DIODE_OFF_COLOR
                    photodiode.draw()

                    image_stim.draw()
                    fixation.draw()
                    win.flip()

                    # Reset trigger on the frame after it was set (frame 1)
                    if fn == 1:
                        reset_trigger(port)

                    # Response check
                    keys = event.getKeys(keyList=[RESPOND_CHAR, "escape"])
                    for k in keys:
                        if k == "escape":
                            win.close()
                            core.quit()
                        if k == RESPOND_CHAR and DO_FIXATION_TASK:
                            send_trigger(port, TRIGGER_RESPONSE)
                            if (fix_change_idx > 0 and fix_has_changed
                                    and not fix_chgs_detected[fix_change_idx - 1]):
                                rt = trial_clock.getTime() - time_of_last_fix_change
                                response_times[fix_change_idx - 1] = rt
                                response_frame_nums[fix_change_idx - 1] = frame_count
                                fix_chgs_detected[fix_change_idx - 1] = True

                    frame_count += 1

                if stimulus_number_error:
                    break
            # ── end frame loop ────────────────────────────────

            # Block end trigger
            send_trigger(port, TRIGGER_BLOCK_END)
            core.wait(0.01)
            reset_trigger(port)

            diode_stimulator.setAutoDraw(False)

            print(f"   {block_label} done — last frame: {frame_count}, "
                  f"stim_num: {stim_num}")

            # ── Save fixation task data for this block ────────
            if DO_FIXATION_TASK:
                for i in range(len(fix_chg_frames)):
                    fixation_log.append({
                        "participant_id": subject_id,
                        "session": session,
                        "condition": condition,
                        "block": block_idx + 1,
                        "fix_change_frame": fix_chg_frames[i],
                        "fix_change_time": f"{fix_chg_times[i]:.6f}",
                        "detected": fix_chgs_detected[i],
                        "response_time": f"{response_times[i]:.6f}",
                        "response_frame": response_frame_nums[i],
                    })

            # Post-block wait with response collection
            fixation.color = NORMAL_FIX_COLOR
            fixation.draw()
            photodiode.color = DIODE_OFF_COLOR
            photodiode.draw()
            win.flip()
            wait_clock.reset()
            while wait_clock.getTime() < WAIT_DURATION_S:
                keys = event.getKeys(keyList=[RESPOND_CHAR, "escape"])
                for k in keys:
                    if k == "escape":
                        win.close()
                        core.quit()
                    if (k == RESPOND_CHAR and DO_FIXATION_TASK
                            and fix_change_idx > 0 and fix_has_changed
                            and not fix_chgs_detected[fix_change_idx - 1]):
                        rt = trial_clock.getTime() - time_of_last_fix_change
                        response_times[fix_change_idx - 1] = rt
                        response_frame_nums[fix_change_idx - 1] = frame_count
                        fix_chgs_detected[fix_change_idx - 1] = True

            # ── Incremental save after each block ─────────────
            _save_onset_log(onset_log, out_dir, subject_id, session)
            if DO_FIXATION_TASK:
                _save_fixation_log(fixation_log, out_dir, subject_id, session)

        # ── end block loop ────────────────────────────────────

    # ── End of experiment ─────────────────────────────────────
    show_text_and_wait(
        win,
        "L'expérience est terminée.\n\n"
        "Merci pour votre participation !\n\n"
        "Appuyez sur ESPACE pour quitter.",
    )

    # Final save
    _save_onset_log(onset_log, out_dir, subject_id, session)
    if DO_FIXATION_TASK:
        _save_fixation_log(fixation_log, out_dir, subject_id, session)
    _save_run_info(out_dir, subject_id, session, frame_rate, actual_freq,
                   frames_per_cycle, frame_on, condition_order, onset_log)

    win.close()
    core.quit()


# ═══════════════════════════════════════════════════════════════
#  FILE I/O
# ═══════════════════════════════════════════════════════════════

def _save_onset_log(log, out_dir, subject_id, session):
    path = os.path.join(out_dir, f"{subject_id}_sess{session}_onsets.csv")
    if not log:
        return
    fieldnames = list(log[0].keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(log)


def _save_fixation_log(log, out_dir, subject_id, session):
    path = os.path.join(out_dir, f"{subject_id}_sess{session}_fixation.csv")
    if not log:
        return
    fieldnames = list(log[0].keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(log)


def _save_run_info(out_dir, subject_id, session, frame_rate, actual_freq,
                   frames_per_cycle, frame_on, condition_order, onset_log):
    path = os.path.join(out_dir, f"{subject_id}_sess{session}_runInfo.txt")
    lines = [
        f"Subject ID: {subject_id}",
        f"Session: {session}",
        f"Detected refresh rate (Hz): {frame_rate:.2f}",
        f"Actual stimulation frequency (Hz): {actual_freq:.2f}",
        f"Target frequency (Hz): {TARGET_FREQ}",
        f"Frames per cycle: {frames_per_cycle}",
        f"Frames ON: {frame_on}",
        f"Frames OFF: {FRAME_OFF}",
        f"Block duration (s): {BLOCK_DURATION_S}",
        f"Blocks per condition: {NUM_BLOCKS_PER_CONDITION}",
        f"Conditions: {CONDITIONS}",
        f"Condition order: {condition_order}",
        f"Stim pattern: {STIM_PATTERN}",
        f"Sinusoidal stim: {SINUSOIDAL_STIM}",
        f"Fade in: {FADE_IN} ({FADE_IN_CYCLES} cycles)",
        f"Fade out: {FADE_OUT} ({FADE_OUT_CYCLES} cycles)",
        f"Random size variation: {RANDOMLY_VARY_SIZE}",
        f"Size range (%): {SIZE_PERCENT_RANGE}",
        f"Fixation task: {DO_FIXATION_TASK}",
        f"Fix changes per block: {NUM_FIX_CHANGES}",
        f"Fix change duration (s): {FIX_CHANGE_DUR_S}",
        f"Min secs between fix changes: {MIN_SECS_BTW_FIX_CHGS}",
        f"Triggers enabled: {USE_TRIGGERS}",
        f"Total stimuli logged: {len(onset_log)}",
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Run info saved to: {path}")


if __name__ == "__main__":
    main()

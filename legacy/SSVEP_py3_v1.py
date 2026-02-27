# Author: Joseph M. Arizpe at Harvard Medical School.
# Modified to remove EEG port requirements, remove imghdr, and bypass frame-rate detection issues.

from psychopy import visual, core, event, gui
import os
import sys
import random
import math
import csv

ACTUAL_SCREEN_RESOLUTION = [1920, 1080]  # safer default


# -------------------------
# SIMPLE IMAGE FILE CHECK
# -------------------------
def is_image_file(path):
    valid_ext = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")
    return path.lower().endswith(valid_ext)


class SSVEP:
    def __init__(self, mywin=visual.Window(size=ACTUAL_SCREEN_RESOLUTION,
                                           color=[138, 138, 138], colorSpace='rgb255',
                                           fullscr=False, monitor='testMonitor', units='deg'),
                 frame_off=1, target_freq=6, blockdur=5.0,
                 fname='SSVEP', numblocks=1, waitdur=2,
                 randomlyVarySize=False, isSinusoidalStim=True,
                 doFixationTask=True, numFixColorChanges=8,
                 fixChangeDurSecs=0.2, minSecsBtwFixChgs=1.2,
                 showDiodeStimulator=True):

        self.baseStimDir = 'stimuli'
        self.StimDir = ['mammals', 'tools']
        self.StimPattern = [4, 1]
        self.doRandomList = False
        self.mywin = mywin
        self.stimSize = [20, 20]
        self.randomlyVarySize = randomlyVarySize
        self.fadeIn = True
        self.fadeInCycles = 2.0
        self.fadeOut = True
        self.fadeOutCycles = 2.0
        self.sizePercentRange = [74, 120]
        self.sizePercentSteps = 2
        self.isSinusoidalStim = isSinusoidalStim
        self.doFixationTask = doFixationTask
        self.normalFixColor = [0, 0, 0]
        self.detectFixColor = [255, 0, 0]
        self.showDiodeStimulator = showDiodeStimulator
        self.diodeOnStimColor = [255, 255, 255]
        self.diodeOffStimColor = [0, 0, 0]
        self.respondChar = 'space'

        self.pattern2 = visual.ImageStim(win=self.mywin, units='deg',
                                         pos=[0, 0], size=self.stimSize,
                                         opacity=1, interpolate=True)

        self.fixation = visual.TextStim(win=self.mywin, text='+', units='deg',
                                        height=0.5, pos=[0, 0],
                                        color=self.normalFixColor, colorSpace='rgb255')

        self.diodeStimulator = visual.Rect(win=self.mywin, width=0.1, height=0.1,
                                           pos=[-0.9, -0.9], fillColor=[0, 0, 0],
                                           colorSpace='rgb255')

        # -------------------------------
        # FRAME RATE FIX
        # -------------------------------
        self.frameRate = self.mywin.getActualFrameRate()

        if self.frameRate is None:
            print("WARNING: PsychoPy could not detect frame rate. Using default 60 Hz.")
            self.frameRate = 60.0

        print("Using frame rate:", self.frameRate)

        self.targFreq = target_freq
        self.framesPerCycle = max(1, round(self.frameRate / self.targFreq))
        self.StimulationFreq = self.frameRate / self.framesPerCycle

        print("Actual Stimulation Frequency:", self.StimulationFreq)
        print("Frames Per Cycle:", self.framesPerCycle)

        self.frame_on = max(1, self.framesPerCycle - frame_off)
        self.frame_off = frame_off

        self.blockdur = blockdur
        self.fname = fname
        self.numblocks = numblocks
        self.waitdur = waitdur

        # Stimulus list
        self.stimFileName = self.Generate_stimList()

        with open(self.stimFileName) as f:
            reader = csv.reader(f, delimiter="\t")
            self.stimMat = [row[0] for row in reader]

        # Fixation task setup
        if self.doFixationTask and len(self.stimMat) > 0:
            framesPerSec = self.StimulationFreq * self.framesPerCycle
            self.numFixColorChanges = numFixColorChanges
            self.numFramesFixChange = int(round(framesPerSec * fixChangeDurSecs))

            totFrames = len(self.stimMat) * self.framesPerCycle
            nEvents = min(self.numFixColorChanges,
                          max(1, totFrames // (2 * self.numFramesFixChange)))
            self.fixChgFrames = sorted(random.sample(
                range(self.numFramesFixChange, totFrames - self.numFramesFixChange),
                nEvents
            ))
            self.fixChgBackFrames = [x + self.numFramesFixChange for x in self.fixChgFrames]
            self.fixChgsDetected = [0] * len(self.fixChgFrames)
        else:
            self.doFixationTask = False

        # Size variation
        if self.randomlyVarySize:
            self.randScalingVals = [random.uniform(0.74, 1.2) for _ in self.stimMat]
        else:
            self.randScalingVals = [1.0] * len(self.stimMat)

    def Generate_stimList(self):
        name = f"Stimuli_list_{self.fname}.txt"
        StimList = []

        AllStims = []
        for folder in self.StimDir:
            folderPath = os.path.join(self.baseStimDir, folder)
            if not os.path.isdir(folderPath):
                print(f"WARNING: folder not found: {folderPath}")
                AllStims.append([])
                continue

            files = [
                os.path.join(folderPath, f)
                for f in os.listdir(folderPath)
                if is_image_file(os.path.join(folderPath, f))
            ]
            if len(files) == 0:
                print(f"WARNING: no valid images found in {folderPath}")
            random.shuffle(files)
            AllStims.append(files)

        if any(len(lst) == 0 for lst in AllStims):
            print("ERROR: No images found in one or more stimulus folders.")
            print("Make sure you have e.g. stimuli/mammals/*.png and stimuli/tools/*.png")
            core.quit()

        stimInds = [0, 0]
        totalCycles = self.numblocks * int(math.ceil(self.blockdur * self.targFreq))

        for _ in range(totalCycles):
            for stimType in range(2):
                for _ in range(self.StimPattern[stimType]):
                    StimList.append(AllStims[stimType][stimInds[stimType]])
                    stimInds[stimType] += 1
                    if stimInds[stimType] >= len(AllStims[stimType]):
                        stimInds[stimType] = 0
                        random.shuffle(AllStims[stimType])

        with open(name, "w") as f:
            for stim in StimList:
                f.write(stim + "\n")

        return name

    def waitForTrigger(self):
        msg = visual.TextStim(self.mywin, text="Press any key to begin")
        msg.draw()
        self.mywin.flip()
        event.waitKeys()

    def stop(self):
        self.mywin.close()
        core.quit()

    def start(self):
        self.waitForTrigger()

        self.thisFrame = 0
        self.stimNum = 0

        for block in range(self.numblocks):

            blockClock = core.Clock()

            while blockClock.getTime() < self.blockdur:

                # OFF frames
                for _ in range(self.frame_off):
                    self.fixation.draw()
                    self.mywin.flip()
                    self.thisFrame += 1

                # ON frames
                if self.stimNum >= len(self.stimMat):
                    break

                self.pattern2.image = self.stimMat[self.stimNum]
                self.pattern2.size = [s * self.randScalingVals[self.stimNum] for s in self.stimSize]

                for _ in range(self.frame_on):
                    self.pattern2.draw()
                    self.fixation.draw()
                    self.mywin.flip()
                    self.thisFrame += 1

                self.stimNum += 1

        self.stop()


class InputBox:
    def __init__(self):
        dlg = gui.Dlg(title="SSVEP Menu")
        dlg.addField("Participant:", "0")
        dlg.addField("Session:", "001")
        dlg.addField("Frequency Target:", 6)
        dlg.addField("Block Duration (s):", 20)
        dlg.addField("Inter-block Time (s):", 2)
        dlg.addField("Number of Blocks:", 1)

        dlg.show()

        if not dlg.OK:
            core.quit()

        data = dlg.data
        self.participant = data[0]
        self.session = data[1]
        self.freq = int(data[2])
        self.duration = int(data[3])
        self.wait = int(data[4])
        self.blocks = int(data[5])

    def file(self):
        return f"sub{self.participant}_sess{self.session}"


# -------------------------
# MAIN EXECUTION
# -------------------------

exp = InputBox()

stimuli = SSVEP(
    frame_off=1,
    target_freq=exp.freq,
    fname=exp.file(),
    blockdur=exp.duration,
    numblocks=exp.blocks,
    waitdur=exp.wait,
    randomlyVarySize=False,
    isSinusoidalStim=True,
    doFixationTask=True,
    showDiodeStimulator=True
)

stimuli.mywin.fullscr = True
stimuli.mywin.flip()
stimuli.start()

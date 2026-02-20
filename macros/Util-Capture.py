import sys
from os.path import join, basename, dirname
import os
import stat

FormvarIndex = 1
PolygonIndex = 2
FocusPointIndex = 3

VolumeExperiments = ['RC3', 'RPC3', 'miniRCx1', 'MiniTest1']

def Capture(CookFirst:bool) -> None:
    CurrentNotes = CurrentSampleNotes()
    assert CurrentNotes is not None, "No sample notes have been entered!"
    assert len(CurrentNotes) == 1, "Capture macro does not yet support multiple section captures"

    # Prompt the user to create capture notes
    PromptForProcessNotes()
    CurrentNotes = CurrentSampleNotes()
    assert CurrentNotes is not None, "No sample notes have been entered!"

    if not CookFirst:
        print("This macro performs an image stabilization calibration,")
    else:
        print("This macro performs a high mag cook, image stabilization calibration,")
    print("verifies the beam current is stable, focuses the scope and captures")
    print("a montage.")
    print()
    print("The Navigator table should contain the following entries for this macro:")
    print("    Item1: A point surrounded by at least 10um of empty formvar")
    print("                  used for the current stability check")
    print("    Item2: The 2D region of interest to be captured")
    print("    Item3: An optional point to focus upon. The point should contain")     
    print("                  sufficient texture for autofocus to succeed. If not specified")
    print("                  the center of the capture region will be used instead.")
    print()

    NumNavItems = sem.ReportNumTableItems()

    if NumNavItems < 1:
        print()
        print("ERROR: Nav table does not have items described in help text above.")
        print("Exiting")
        return
    elif NumNavItems < 2:
        print()
        print("ERROR: Nav table does not have a point in empty formvar for filament stability check.")
        print("Exiting")
        return

    StartingMag, LowMag = sem.ReportMag()

    if LowMag == 1:
        print("Attempting Capture in Low Mag mode, aborting.")
        print("Go to high magnification mode before using this macro.")
        return

    print(sem.NavItemFileToOpen(PolygonIndex))

    # TODO get Block from the label of the navigator point instead of disturbing CurrentSampleNotes, when multiple captures are implemented
    Block, Notes = CurrentNotes.popitem(last=False)
    _, _, _, _, _, Investigator, Experiment, _, _, _, _, _, _, _ = Notes
    CurrentNotes[Block] = Notes
    CurrentNotes.move_to_end(Block, last=False)
    WriteSampleNotes(CurrentNotes)
    CaptureDir = GetCaptureDir(Block)
    OverviewFilename = GetOverviewFilename(Block)

    ### FOCUS ###
    if NumNavItems < 3:
        sem.MoveToNavItem(PolygonIndex)
    else:
        sem.MoveToNavItem(FocusPointIndex)

    sem.Delay(3)
    sem.Focus()

    ### CALIBRATE IMAGE SHIFT ###
    try:
        sem.CalibrateImageShift()
    except:
        print(f"Image shift failed with {sys.exc_info()[0]}. Not interrupting capture per Jaap's recommendation.")

    sem.ScreenDown()

    sem.ReportAlpha()
    sem.ReportBeamShift()
    sem.ReportBeamTilt()

    if CookFirst:
        #### COOKING ####
        print("Cooking Begins!")
        StartingSpotSize = sem.ReportSpotSize()

        # Don't set spot size for high mag cook, because the beam will move on TEM1
        # sem.SetSpotSize(2)

        sem.PreCookMontage(PrecookMontageD, 2, 0, 0)

        # print("Restoring spot size after cook")
        # sem.SetSpotSize(StartingSpotSize)

        print("Cooking done!")
        sem.ReportClock()

    ###  BEAM STABILITY CHECK ####
    # Move the stage to the area we've been told to use
    sem.MoveToNavItem(FormvarIndex)

    try:
        WaitForStableFilament()
    except:
        print(f"Error {sys.exc_info()[0]} from WaitForStableFilament python. Trying regular version") 
        sem.Call("WaitForStableFilament")

    ### Center on montage and capture ###
    sem.MoveToNavItem(PolygonIndex)

    try:
        SendStart()
    except:
        sem.CallFunction("Notifications::SendMessage", f"Failed to send start notification from Python because of {sys.exc_info()[0]}")
        sem.CallFunction("Notifications::SendStart")

    try:
        sem.Montage()
        # Neutralize the stage before a rod change
        MoveStageTo(0, 0)
    except:
        Message = f"Montage failed with error {sys.exc_info()[0]} on {ScopeName}"
        try:
            SendMessage(Message)
        except:
            sem.CallFunction("Notifications::SendMessage", "Failed to send montage error message from Python")
            sem.CallFunction("Notifications::SendMessage", Message)
        return

    # Send the overview to Slack
    TakeSnapshot(True, OverviewFilename, Overview=True)

    # Copy the capture to DROPBOX
    ExperimentDir = basename(dirname(CaptureDir))
    # This should copy core builds by investigator name instead of experiment name:
    DestinationDir = ExperimentDir if Experiment in VolumeExperiments else Investigator
    SectionDir = basename(CaptureDir)
    #os.chmod(SectionDir, stat.S_IRUSR)
    if CopyDir(join(DataPath, ExperimentDir), join(CopyPath, DestinationDir), SectionDir):
        SendStop(ExperimentDir, SectionDir)
    else:
        SendMessage(f"Failed to copy {CaptureDir} to DROPBOX")
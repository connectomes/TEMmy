#!Python3.9
#MacroName Captures - Python
#include WaitForStableFilament - Python
#include CopyFunctions - Python
#include Notifications - Python
#include Snapshot - Python
import serialem as sem
import sys

def Capture(CookFirst):
    if not CookFirst:
        print("This macro performs an image stabilization calibration,")
    else:
        print("This macro performs a high mag cook, image stabilization calibration,")
    print("verifies the beam current is stable, focuses the scope and captures")
    print("a montage.")
    print()
    print("The Navigator table should contain the following entries for this macro:")
    print("    Item1: The 2D region of interest to be captured")
    print("    Item2: A point surrounded by at least 10um of empty formvar")
    print("                  used for the current stability check")
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

    print(sem.NavItemFileToOpen(1))

    # Prompt the user for the directory the capture will be placed
    sem.EnterString("CaptureDir", "Directory of the capture, relative to your data drive?")
    CaptureDir = sem.GetVariable("CaptureDir")

    # Prompt the user to create capture notes
    sem.RunExternalTool("1")

    ### FOCUS ###
    if NumNavItems < 3:
        sem.MoveToNavItem(1)
    else:
        sem.MoveToNavItem(3)

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

        sem.PreCookMontage(int(sem.GetVariable("PrecookMontageD")), 2, 0, 0)

        # print("Restoring spot size after cook")
        # sem.SetSpotSize(StartingSpotSize)

        print("Cooking done!")
        sem.ReportClock()

    ###  BEAM STABILITY CHECK ####
    # Move the stage to the area we've been told to use
    sem.MoveToNavItem(2)

    try:
        WaitForStableFilament()
    except:
        print(f"Error {sys.exc_info()[0]} from WaitForStableFilament python. Trying regular version") 
        sem.Call("WaitForStableFilament")

    ### Center on montage and capture ###
    sem.MoveToNavItem(1)

    try:
        SendStart()
    except:
        sem.CallFunction("Notifications::SendMessage", "Failed to send start notification from Python")
        sem.CallFunction("Notifications::SendStart")

    try:
        sem.Montage()
    except:
        Message = f"Montage failed with error {sys.exc_info()[0]} on {sem.GetVariable('ScopeName')}"
        try:
            SendMessage(Message)
        except:
            sem.CallFunction("Notifications::SendMessage", "Failed to send montage error message from Python")
            sem.CallFunction("Notifications::SendMessage", Message)
        return

    # Send the overview to Slack
    TakeSnapshot(True, f"overview{CaptureDir}")

    # Copy the capture to DROPBOX
    # Try python CopyFunctions first:
    try:
        CopyDir(f"{sem.GetVariable('DataPath')}/{CaptureDir}", sem.GetVariable("CopyPath"), CaptureDir)
    except:
        sem.CallFunction("Notifications::SendMessage", f"Python CopyDir failed with error {sys.exc_info()[0]}. Trying again with old version")
        sem.SetVariable("CopyTarget", sem.GetVariable("CopyPath"))
        sem.SetVariable("TargetDirName", CaptureDir)
        sem.SetVariable("CopySource", f"{sem.GetVariable('DataPath')}\\{CaptureDir}")
        sem.CallFunction("CopyFunctions::CopyDir")

    sem.CallFunction("Notifications::SendStop")
# This file is named with a Z so it comes after every other Python function in Util files is defined

RodChangeSteps:list[Step] = [
    DoAutomatically(TurnOffFilament),
    TellOperatorTEM("Pull the rod handle straight out until it stops, then twist it counter-clockwise until it stops."),
    TellOperatorTEM("One more time, pull the rod handle straight out until it stops, then twist it counter-clockwise until it stops. Then flip the PUMP switch to AIR. Then WAIT for V16 and V18 in TEM Center to turn green, then back to gray."),
    TellOperatorTEM("Pull the rod all the way out, and go put the next grid in it."),
    # Neutralize the stage before putting a new rod in it, so the range of stage movement doesn't get clipped on the new specimen
    DoAutomatically(lambda: MoveStageTo(0, 0)),
    TellOperatorTEM("Line up the knob on the rod with the opening in the specimen chamber. Push the rod in until it stops."),
    TellOperatorTEM("Keep your hand on the rod, and flip the switch from AIR to PUMP. A yellow light should turn on. If it doesn't, make sure the rod is in as far as it will go, and keep your hand on it. Wait for the specimen chamber to pump down and turn Green in TEM Center."),
    TellOperatorTEM("Twist the rod handle clockwise and allow it to be pulled inward. Twist clockwise again and the rod should go in all the way."),
]

NewSpecimenSteps:list[Step] = [
    DoAutomatically(ClearSampleNotes),
    # DoAutomatically(ClearDataDrive),
    DependingOnYesNo("Is the sample already loaded in the scope?", SkipSteps(RodChangeSteps), RunNextStep)
] + RodChangeSteps + [
    DependingOnScope(DoNothing, TellOperator("Wait for the Penning Gauge to turn on (Green) and stabilize below 30.")),
    DoAutomatically(lambda: SetMagIndex(LowMag150)),
    TellOperatorTEM("Remove the aperture by turning the dial to the red dot."),
    DoAutomatically(TurnOnFilament),
    DependingOnScope(DoAutomatically(lambda: SetSpotSize(3)),DoAutomatically(lambda: SetSpotSize(2))),
    DoAutomatically(ScreenDown),
    TellOperatorSEM("Scroll the stage to find a region of formvar, and click 'Add Stage Pos' in the navigator window."),
]

LowMagCookSteps:list[Step] = [
    DoAutomatically(lambda: SetSpotSize(1)),
    TellOperatorTEM("Scroll the stage to the center of the tissue. Remove the mirror. Center and tighten the beam to the inner brackets. Clicking OK will start the 7-minute cook timer"),
    DoAutomatically(lambda: LowMagCook(7)),
]

AfterMontageSteps:list[Step] = [
    DependingOnYesNo("Does the overview look good enough to move onto new tissue?", DoAutomatically(TurnOffFilament), TellOperator("When selecting your next tutorial, choose the 'recapture' variation and do not switch samples.")),
    TellOperatorSEM("Close SerialEM. Click 'No' when it asks you whether to save anything. Then open SerialEM again and click 'Start Tutorial' for your next capture.")
]

AcquireAtItemsMessage = "In the menubar, click Navigator -> AcquireAtItems. Choose '*'. Leave FilamentManager selected, and click OK. Then move the mirror out of the way."

# Pass these as arguments to SwitchToHighMagSteps for readability
SpotSize1:int = 1
SpotSize2:int = 2
SpotSize3:int = 3

ManuallyCheckCenterPoint:Step = DependingOnYesNo("Does this snapshot show the center point correctly and visibly?", DoAutomatically(lambda: print("")), TellOperatorSEM("Manually correct and re-take the center point image. When you click 'Next step', it will be saved."))

ManuallyCheckControlPoints:Step = DependingOnYesNo("Does this snapshot show the control points correctly and visibly?", DoAutomatically(lambda: print("")), TellOperatorSEM("Manually correct and re-take the control points image. When you click 'Next step', it will be saved."))

def OpenLastSnapshot(recap:bool, investigator:str, volume:str, mag:int) -> Step:
    def step() -> None:
        if recap:
            TellOperator(f"Open DROPBOX/TEMSnapshots and open the closest {investigator} {volume} snapshot to your section at x{mag}")()
        else:
            try:
                startfile(glob(join(DropboxPath, "TEMSnapshots", f"{investigator} {volume} * x{mag} *.jpg"))[-1])
                RunNextStep()
            except:
                TellOperator(f"Open DROPBOX/TEMSnapshots and open the latest {investigator} {volume} snapshot at x{mag}")()
    return step

def SwitchTo600MagSteps(recap:bool, investigator:str, volume:str, Mag:int, MagIndex:int, SpotSize:int, ChangeAperture:bool, CenterAperture:bool, CenterPoint:bool) -> list[Step]:
    return [
        DoAutomatically(lambda: SetBeamBlank(True)),
        DoAutomatically(lambda: SetMagIndex(MagIndex)),
        DoAutomatically(lambda: SetSpotSize(SpotSize))
    ] + [(
        TellOperatorTEM("Ensure first aperture is in."))]+([
        OpenLastSnapshot(recap, investigator, volume, Mag),
        DoAutomatically(Record),
        TellOperatorSEM(f"Center over 4 control points at a time. {newline} Find the  control points at {Mag}x, and use 'Move Item' to relocate the control points to the correct location."),
        DoAutomatically(Record),
        ManuallyCheckControlPoints,
        DoAutomatically(lambda: TakeSnapshotWithNotes("", False,NumberDuplicates=True)),
    ] if CenterPoint else [])

def SwitchToHighMagSteps(recap:bool, investigator:str, volume:str, Mag:int, MagIndex:int, SpotSize:int, ChangeAperture:bool, CenterAperture:bool, CenterPoint:bool, FocusSteps:list[Step]) -> list[Step]:
    return [
        DoAutomatically(lambda: SetBeamBlank(True)),
        DoAutomatically(lambda: SetMagIndex(MagIndex)),
        DoAutomatically(lambda: SetSpotSize(SpotSize))
    ] + ([
        TellOperatorTEM("Ensure second aperture is in."),
        DependingOnScope(TellOperatorTEM("Spread the beam by several turns (by turning the 'brightness' knob clockwise.)"), DoNothing),
        DoAutomatically(ScreenDown),
        TellOperatorTEM("Use the X/Y dials on the upper left side of the microscope column to center the aperture.")
    ] if ChangeAperture else []) + ([
        TellOperatorTEM(f"Spread the beam by several turns (by turning the 'brightness' knob clockwise.)"), DoNothing,
        DoAutomatically(ScreenDown),
        TellOperatorTEM("Use the X/Y dials on the upper left side of the microscope column to center the aperture.")
    ] if CenterAperture else[]) + FocusSteps + [
        DoAutomatically(Record)
    ] + ([
        OpenLastSnapshot(recap, investigator, volume, Mag),
        TellOperatorSEM(f"Find the center or control points at {Mag}x, and use 'Move Item' to relocate the centerpoint/ control points to the correct location."),
        DoAutomatically(lambda: MoveToNavItem()),
        DoAutomatically(Record),
        ManuallyCheckCenterPoint,
        DoAutomatically(lambda: TakeSnapshotWithNotes("", False,NumberDuplicates=False)),
    ] if CenterPoint else [])

FastFocusSteps:list[Step] = [
    DoAutomatically(ScreenDown),
    TellOperatorTEM("Tighten the beam, center it, and use image wobble and the focus knob to adjust focus. Turn off wobble. Make sure the beam is spread around 100 Current Density.")
]

DetailedFocusSteps:list[Step] = [
    DoAutomatically(ScreenDown),
    TellOperatorTEM("Turn the brightness knob counter-clockwise to tighten the beam, then center it with the X/Y knobs on the control panel."),
    DependingOnScope(TellOperatorTEM("Turn on Image Wobble X and Image Wobble Y using the control panel."), TellOperatorTEM("Turn on Image Wobble using the control panel.")),
    TellOperatorTEM("Put the mirror in using the lever to the right of the microscope column."),
    TellOperatorTEM(f"Look through the binoculars and use the focus knob to make the 2 shaking images line up and stay still. {newline} Turn off wobble."),
    TellOperatorTEM("Turn the brightness knob clockwise to spread the beam until Current Density is close to 100.")
]

ChooseMontageMacro:Step = DependingOnYesNo("Are there any holes in the section or formvar?", TellOperatorSEM(AcquireAtItemsMessage.replace("*", "CalibrateAndRecapturePy")), TellOperatorSEM(AcquireAtItemsMessage.replace("*", "HighMagCookPy")))
UseRecaptureMacro:Step = TellOperatorSEM(AcquireAtItemsMessage.replace("*", "CalibrateAndRecapturePy"))

def FinalSteps(detailed:bool, core:bool, recap:bool) -> list[Step]:
    MontageStep:Step = ChooseMontageMacro
    if recap:
        MontageStep = UseRecaptureMacro
    
    steps:list[Step] = [
        DoAutomatically(Autofocus),
        DoAutomatically(Record),
    ]
    if detailed:
        steps.append(TellOperatorSEM("If the focus looks good, click 'Next Step'. If not, redo the focus, click 'Autofocus', then 'Record.' Keep doing this until it looks good."))
        if not core:
            steps.append(TellOperatorSEM("If the green number representing the circle's center has shifted from where you put it, use 'Move item' to fix it, then click 'Stop Moving.'"))
        steps.append(MontageStep)
        steps += AfterMontageSteps
    
    return steps


# This file is named with a Z so it comes after every other Python function in Util files is defined

def VerticalVolumeSteps(investigator:str, name:str, detailed:bool, recap:bool) -> list[Step]:
    FocusSteps = DetailedFocusSteps if detailed else FastFocusSteps
    
    return [
        OpenLastSnapshot(recap, investigator, name, 150),
        TellOperatorSEM(f"Locate the image of the previous section at 150x. {newline} Click 'Add Points' in the navigator window and place the control points of the ROI. Then click 'Stop Adding Points'.{newline} {newline} If no image appears or image is washed out, check current density and press 'Record' to have image for placing new control points"),
        TellOperatorSEM("Select each of the corner points and type 'C' on the keyboard to mark them as corner points."),
        DoAutomatically(lambda: MoveToNavItem(PolygonIndex)),
        DoAutomatically(Record),
        ManuallyCheckControlPoints,
        DoAutomatically(lambda: TakeSnapshotWithNotes("", False))
    ] + SwitchTo600MagSteps(recap, investigator, name, 600, HighMag600, SpotSize=3, ChangeAperture=True, CenterAperture=False, CenterPoint=True)+ SwitchTo600MagSteps(recap, investigator, name, 600, HighMag600, SpotSize=3, ChangeAperture=True, CenterAperture=False, CenterPoint=True)+SwitchToHighMagSteps(recap, investigator, name, 2000, HighMag2000, SpotSize=2, ChangeAperture=True, CenterAperture=True, CenterPoint=False, FocusSteps=FocusSteps) + [
        TellOperatorSEM(f"In the menubar, click Navigator -> Montaging and Grids -> Polygon from Corners {newline} When prompted select ok for delete all corners "),
        DoAutomatically(lambda: SetMagIndex(HighMag5000)),
        TellOperatorSEM(f"With the polygon selected, check the Navigator checkboxes for 'Aquire', 'New File At Item', 'Montaged Images', 'Fit Montage to Polygon'. {newline} {newline} In setup window: {newline} Make sure overlap is set to 15% {newline} 'Go from center out and anchor at 2000x' is active {newline} click ok. Then select the generated idoc file. Choose to overwrite it."),
        DoAutomatically(lambda: MoveToNavItem(PolygonIndex)),
        DoAutomatically(lambda: SetSpotSize(2)),
        DoAutomatically(ScreenDown)
    ] + FocusSteps + FinalSteps(detailed, False, recap)


Steps["miniRCx1"] = NewSpecimenSteps + LowMagCookSteps + VerticalVolumeSteps("Sigulinsky", "miniRCx1", True, False)
Steps["miniRCx1 Recapture"] = NewSpecimenSteps + VerticalVolumeSteps("Sigulinsky", "miniRCx1", True, True)

Steps["miniRCx1 Fast"] = NewSpecimenSteps + LowMagCookSteps + VerticalVolumeSteps("Sigulinsky", "miniRCx1", False, False)
Steps["miniRCx1 Recap Fast"] = NewSpecimenSteps + VerticalVolumeSteps("Sigulinsky", "miniRCx1", False, True)

 
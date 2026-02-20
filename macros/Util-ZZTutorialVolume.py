# This file is named with a Z so it comes after every other Python function in Util files is defined

def MainVolumeSteps(investigator:str, name:str, radius:int, detailed:bool, recap:bool) -> list[Step]:
    FocusSteps = DetailedFocusSteps if detailed else FastFocusSteps
    
    return [
        OpenLastSnapshot(recap, investigator, name, 150),
        TellOperatorSEM(f"Locate the center point at 150x, click it, and click 'Add Marker' in the navigator window.{newline} {newline} If no im age appears or image is washed out, check current density and press 'Record' to have image for placing new centerpoint"),
        DoAutomatically(lambda: MoveToNavItem(PolygonIndex)),
        DoAutomatically(Record),
        ManuallyCheckCenterPoint,
        DoAutomatically(lambda: TakeSnapshotWithNotes("", False))
    ] + SwitchToHighMagSteps(recap, investigator, name, 600, HighMag600, SpotSize=3, ChangeAperture=True, CenterAperture=False, CenterPoint=True, FocusSteps=[]) + SwitchToHighMagSteps(recap, investigator, name, 2000, HighMag2000, SpotSize=2, ChangeAperture=False, CenterAperture=True, CenterPoint=True, FocusSteps=FocusSteps) + [
        TellOperatorSEM(f"In the menubar, click Navigator -> Montaging and Grids -> Add Circle Polygon. Type {radius}"),
        TellOperatorSEM("In the navigator window, delete every item EXCEPT FOR the formvar reference point and the circle Polygon."),
        DoAutomatically(lambda: SetMagIndex(HighMag5000)),
        TellOperatorSEM(f"With the circle polygon selected, check the Navigator checkboxes for 'Aquire', 'New File At Item', 'Montaged Images', 'Fit Montage to Polygon'. {newline} {newline} In setup window: {newline} Make sure overlap is set to 12% {newline} 'Go from center out and anchor at 2000x' is active {newline} click ok. Then select the generated idoc file. Choose to overwrite it."),
        DoAutomatically(lambda: MoveToNavItem(PolygonIndex)),
        DoAutomatically(lambda: SetSpotSize(2)),
        DoAutomatically(ScreenDown)
    ] + FocusSteps + FinalSteps(detailed, False, recap)

#Not callable because these aren't currently in use.  Repopulate for next mini Hz connectome (RPC3) or full Hz connectome
"""Steps["RC3"] = NewSpecimenSteps + LowMagCookSteps + MainVolumeSteps("Jones", "RC3", 125, True, False)
Steps["RC3 Recapture"] = NewSpecimenSteps + MainVolumeSteps("Jones", "RC3", 125, True, True)

Steps["RC3 Fast"] = NewSpecimenSteps + LowMagCookSteps + MainVolumeSteps("Jones", "RC3", 125, False, False)
Steps["RC3 RecapFast"] = NewSpecimenSteps + MainVolumeSteps("Jones", "RC3", 125, False, True)

Steps["RPC3"] = NewSpecimenSteps + LowMagCookSteps + MainVolumeSteps("Jones", "RPC3", 45, True, False)
Steps["RPC3 Recapture"] = NewSpecimenSteps + MainVolumeSteps("Jones", "RPC3", 45, True, True)

Steps["RPC3 Fast"] = NewSpecimenSteps + LowMagCookSteps + MainVolumeSteps("Jones", "RPC3", 45, False, False)
Steps["RPC3 RecapFast"] = NewSpecimenSteps + MainVolumeSteps("Jones", "RPC3", 45, False, True)"""


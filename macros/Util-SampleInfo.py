import os.path
import os
from os.path import join
from os import makedirs
from typing import Tuple
from typing import cast
from collections import OrderedDict
from typing import Optional
from typing import List
import json

SampleNotes = Tuple[int, str, str, str, int, str, str, str, bool, bool, bool, str, str, str]

SampleNotesFile = "C:/Users/VALUEDGATANCUSTOMER/CurrentSampleNotes.json"
def CurrentSampleNotes() -> Optional[OrderedDict[str, SampleNotes]]:
    if os.path.exists(SampleNotesFile):
        with open(SampleNotesFile, "r") as f:
            return cast(OrderedDict[str, SampleNotes], json.load(f, object_pairs_hook=OrderedDict))
    else:
        return None

def WriteSampleNotes(notes:OrderedDict[str, SampleNotes]) -> None:
    with open(SampleNotesFile, "w") as f:
        json.dump(notes, f)

SampleInfoKeys:List[str] = [
    "Version",
    "Microscope",
    "Block",
    "Grid",
    "Rod",
    "Investigator",
    "Experiment",
    "CapturedBy",
    "CameraGainReference",
    "CameraQuadrantReference",
    "NewFilament",
    "ProcedureChanges",
    "Observations",
    "Notes"
]

Version = 2
Microscope = ScopeName
NumRods = 4
MainInvestigator = "Sigulinsky"
MainExperiment = "miniRCx1"
MainOperator = "Matt B"

def PromptForSampleInfo() -> None:
    Blocks = []
    MoreBlocks = True
    while MoreBlocks:
        Blocks.append(EnterString("Block # / Section # (including recapture letter)", forbidden_chars="_"))
        MoreBlocks = YesNoBox("Any more blocks or sections on this grid?")

    Grid = EnterString("Grid #")
    Rod = EnterInt("Rod #", minvalue=1, maxvalue=NumRods)
    Investigator = EnterString("Investigator", MainInvestigator, forbidden_chars="_")
    Experiment = EnterString("Experiment Series", MainExperiment, forbidden_chars="_")
    CapturedBy = EnterString("Captured By", MainOperator)
    CameraGainReference = YesNoBox("Did you, or are you going to, run Gain reference?")
    CameraQuadrantReference = False
    NewFilament = YesNoBox("Was the filament just changed?")
    ProcedureChanges = ""
    Observations = ""
    OtherNotes = ""

    CurrentNotes = OrderedDict()
    for Block in Blocks:
        Notes = (Version, Microscope, Block, Grid, Rod, Investigator, Experiment, CapturedBy, CameraGainReference, CameraQuadrantReference, NewFilament, ProcedureChanges, Observations, OtherNotes)
        CurrentNotes[Block] = Notes
    WriteSampleNotes(CurrentNotes)
    for Block in Blocks:
        WriteNotesFiles(Block, Notes)

def PromptForProcessNotes() -> None:
    CurrentNotes = CurrentSampleNotes()
    assert CurrentNotes is not None, "No sample notes have been entered!"
    for Block, Notes in CurrentNotes.items():
        Version, Microscope, Block, Grid, Rod, Investigator, Experiment, CapturedBy, CameraGainReference, CameraQuadrantReference, NewFilament, _, _, _ = Notes
        ProcedureChanges = EnterString(f"{Block}: Any changes from normal procedure?")
        Observations = EnterString(f"{Block}: Any observations regarding the capture process or data quality?")
        OtherNotes = EnterString(f"{Block}: Other notes?")
        NewNotes = (Version, Microscope, Block, Grid, Rod, Investigator, Experiment, CapturedBy, CameraGainReference, CameraQuadrantReference, NewFilament, ProcedureChanges, Observations, OtherNotes)
        CurrentNotes[Block] = NewNotes
        WriteNotesFiles(Block, NewNotes)
    WriteSampleNotes(CurrentNotes)

def GetCaptureDir(Block:str) -> str:
    ''' Return the FULL path of the directory where the capture's data is being put '''
    CurrentNotes = CurrentSampleNotes()
    assert CurrentNotes is not None
    Notes = CurrentNotes[Block]
    Experiment = Notes[SampleInfoKeys.index("Experiment")]
    BlockPadded = Block.zfill(4)
    Dir = f"{Experiment}/{BlockPadded}"
    return join(DataPath, Dir)

def GetOverviewFilename(Block:str) -> str:
    ''' Return the full filename where the overview of this capture should be stored '''
    CurrentNotes = CurrentSampleNotes()
    assert CurrentNotes is not None
    Notes = CurrentNotes[Block]
    Investigator = Notes[SampleInfoKeys.index("Investigator")]
    Experiment = Notes[SampleInfoKeys.index("Experiment")]
    BlockPadded = Block.zfill(4)
    Filename = f"overview{Investigator}_{Experiment}_{BlockPadded}"
    return Filename

def WriteNotesFiles(Block:str, Notes:SampleNotes) -> None:
    # Make a data output folder for the block
    BlockFolder = GetCaptureDir(Block)
    makedirs(BlockFolder, exist_ok=True)
    # Write notes to a JSON file
    with open(join(BlockFolder, f"{Block}.json"), "w") as json:
        json.write("{" + newline)
        for idx, key in enumerate(SampleInfoKeys):
            jsonValue = Notes[idx]
            if isinstance(Notes[idx], str):
                jsonValue = f'"{Notes[idx]}"'
            elif isinstance(Notes[idx], bool):
                jsonValue = str(Notes[idx]).lower()

            json.write(f'  "{key}": {jsonValue}')
            if idx != len(SampleInfoKeys) - 1:
                json.write(",")
            json.write(newline)
        json.write("}")

    # Write notes to a TXT file
    with open(join(BlockFolder, f"{Block}.txt"), "w") as txt:
        for idx, key in enumerate(SampleInfoKeys):
            txt.write(f"{key}: {Notes[idx]}{newline}")

    # Make an empty idoc file so the operator doesn't have to type the name
    # IdocPath = join(BlockFolder, f"{Block}.idoc")
    # if not os.path.exists(IdocPath):
    #     with open(IdocPath, "w") as f:
    #         pass
        
        # Set the working directory there, and use it in the next file prompt
        SetWorkingDir(BlockFolder)
        sem.OpenChooserInCurrentDir()
    
def ClearSampleNotes() -> None:
    if os.path.exists(SampleNotesFile):
        os.remove(SampleNotesFile)
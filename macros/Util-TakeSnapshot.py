import sys
from typing import Optional
import os

SnapshotCounterByMag: dict[int, int] = {}

def DetermineFileNumber(folder: str, filename: str, ext: Optional[str]=None) -> int:
   """Check if filename exists, and return the number of files with that name"""
   if ext is None:
      ext = 'jpg'

   increment = 0
   file_letter = chr(ord('A') + increment)
   fullfilename = f"{filename} {file_letter}.{ext}"
   fullpath = os.path.join(folder, fullfilename)
   while os.path.exists(fullpath):
      increment += 1
      file_letter = chr(ord('A') + increment)
      fullfilename = f"{filename} {file_letter}.{ext}"
      fullpath = os.path.join(folder, fullfilename)

   return increment
    

# Function for automated use: saves a snapshot of the current image to our DROPBOX.
# If called with True for the first argument, will also send this image to slack in the #tem-bot channel
def TakeSnapshot(SendToSlack:bool, Name:str, Overview:bool=False, Postfix:Optional[str] = None, NumberDuplicates: bool = False) -> None:
   """
   :param NumberDuplicates: Add a letter if a file with the same name already exists
   """
   assert ':' not in Name and '/' not in Name, f"{Name} is a bad filename for an overview! Remove : and /"
   global SnapshotCounterByMag
   # Reports the current mag; also sets reportedValue2 to 1 if low mag mode, 0 if not
   CurrentMag, LowMag = sem.ReportMag()
   CurrentMag = int(CurrentMag)
   #num_snapshots = SnapshotCounterByMag.get(CurrentMag, 0)
   #SnapshotCounterByMag[CurrentMag] = num_snapshots + 1
   #Filename = f"{Name} x{CurrentMag} {ScopeName}.jpg"
   #FilenameInDropbox = f"{DropboxPath}/{Filename}"
   folder = os.path.join(DropboxPath, "TEMSnapshots")
   if Postfix is None:
     base_filename = f"{Name} x{CurrentMag} {ScopeName}"
   else:
     #We want to generate a filename with a postfix if needed
     base_filename = f"{Name} x{CurrentMag} {Postfix} {ScopeName}"

   print("Postfix=None:",base_filename)
   
   extension = "jpg" 
   if NumberDuplicates:
      increment = DetermineFileNumber(folder, base_filename, extension)
      file_letter = chr(ord('A') + increment)
      if Postfix is None:
         base_filename = f"{Name} x{CurrentMag} {ScopeName} {file_letter}"
      else:
         # We want to generate a filename with a postfix if needed
         base_filename = f"{Name} x{CurrentMag} {Postfix} {ScopeName} {file_letter}"
   print("NumberDuplicates=True:",base_filename)
   print(base_filename)

   final_filename = f"{base_filename}.{extension}"
   fullpath = os.path.join(folder, final_filename)   

    
      # Check if the file exists and add a postfix if it does
      # postfix = "A"  # Start with "A"
      # while os.path.exists(FilenameInDropbox):
      #    # Update filename with current postfix and check again
      #   Filename = f"{base_filename}{postfix}{extension}"
      #   FilenameInDropbox = f"{DropboxPath}/{Filename}"
        
      #   # If the file exists, increment the postfix letter (A -> B -> C ...)
      #   postfix = chr(ord(postfix) + 1)
    
   # If no existing file, use the last generated Filename
   #Filename = f"{base_filename}{postfix}{extension}"
   try:
      if Overview:
         sem.SaveToOtherFile("B", "JPG", "CUR", fullpath)
      else:
         sem.SnapshotToFile(0, 0, "0", "JPG", "CUR", fullpath)

   except:
      SendMessage(f"TakeSnapshot() failed for snapshot {final_filename} with {sys.exc_info()[0]}")
      return

   if SendToSlack:
      SendMessage(f"Snapshot: {final_filename}")

# Function for manual use: Prompts for sample notes and takes a snapshot
def TakeSnapshotWithNotes(Label:Optional[str] = None, Slack:Optional[bool] = None, Postfix:Optional[str] = None, NumberDuplicates: bool = False) -> None:
   Sample = ""
   CurrentNotes = CurrentSampleNotes()
   if CurrentNotes is None:
      PromptForSampleInfo()
      CurrentNotes = CurrentSampleNotes()

   assert CurrentNotes is not None
   if len(CurrentNotes) > 1:
      choices = []
      for key, _ in CurrentNotes.items():
         choices.append(key)
      while len(choices) < 3:
         choices.append("")
      Sample = ManyChoiceBox("Which sample are you snapshotting?", choices)
   else:
      for key, _ in CurrentNotes.items():
         Sample = key

   Investigator = CurrentNotes[Sample][SampleInfoKeys.index("Investigator")]
   Experiment = CurrentNotes[Sample][SampleInfoKeys.index("Experiment")]

   if Label is None:
      Label = EnterString("label")
   if Slack is None:
      Slack = YesNoBox("send snapshot to slack?")

   TakeSnapshot(Slack, f"{Investigator} {Experiment} {Sample} {Label}", Postfix=Postfix, NumberDuplicates=NumberDuplicates)
from dataclasses import dataclass
@dataclass
class NoteEvent:
 on:bool; track:int; note:int; velocity:int=100

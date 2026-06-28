from ..dsp.oscillator import SineOsc
class Synth:
    def __init__(self): self.osc=SineOsc(); self.notes={}
    def note_on(self,n,v): self.notes[n]=v
    def note_off(self,n): self.notes.pop(n,None)

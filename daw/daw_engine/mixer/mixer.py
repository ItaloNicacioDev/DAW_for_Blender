from ..instruments.synth import Synth
class Mixer:
    def __init__(self): self.synth=Synth()
    def note_on(self,t,n,v): self.synth.note_on(n,v)
    def note_off(self,t,n): self.synth.note_off(n)
    def process(self,*a,**k): return None

from ..audio.device import AudioDevice
from .clock import Clock
from ..mixer.mixer import Mixer
class DAWEngine:
    def __init__(self): self.clock=Clock(); self.audio=AudioDevice(); self.mixer=Mixer()
    def start(self): self.audio.start(self.mixer.process)
    def stop(self): self.audio.stop()
    def note_on(self,t,n,v=100): self.mixer.note_on(t,n,v)
    def note_off(self,t,n): self.mixer.note_off(t,n)

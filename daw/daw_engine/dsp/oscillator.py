import math
class SineOsc:
    def sample(self,f,t,sr=48000): return math.sin(2*math.pi*f*t/sr)

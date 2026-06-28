# core/settings.py
"""Configurações globais da DAW."""
class Settings:
    """Armazena preferências do usuário e do sistema."""
    def __init__(self):
        self.audio_device = "Default"
        self.sample_rate = 44100
        self.buffer_size = 256
        self.bpm = 120
        self.time_signature = (4, 4)
        self.theme = "dark"
        # ... outros

    def to_dict(self):
        return {
            'audio_device': self.audio_device,
            'sample_rate': self.sample_rate,
            'buffer_size': self.buffer_size,
            'bpm': self.bpm,
            'time_signature': self.time_signature,
            'theme': self.theme
        }

    def from_dict(self, data):
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
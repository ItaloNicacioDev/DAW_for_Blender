# core/state.py
"""Estado global do aplicativo (modo, seleção, etc.)."""
class State:
    """Mantém variáveis de estado como seleção, modo de edição, etc."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.mode = "object"  # "object", "edit", "paint", etc.
            cls._instance.selected_tracks = []
            cls._instance.selected_clips = []
            cls._instance.cursor_position = 0.0  # em segundos
            cls._instance.loop_start = 0.0
            cls._instance.loop_end = 4.0
        return cls._instance

    def select_track(self, track):
        self.selected_tracks.append(track)

    def deselect_all(self):
        self.selected_tracks.clear()
        self.selected_clips.clear()
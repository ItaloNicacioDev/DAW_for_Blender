# core/registry.py
"""Registro de classes, efeitos, instrumentos, etc."""
class Registry:
    """Armazena e fornece acesso a objetos registrados."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._data = {}
        return cls._instance

    def register(self, key, obj):
        self._data[key] = obj

    def get(self, key):
        return self._data.get(key)

    def list(self):
        return list(self._data.keys())

# Exemplo de uso:
# registry = Registry()
# registry.register('compressor', CompressorEffect)
# registry.register('synth', SynthInstrument)
# modules/effects/eq.py
"""
Modelo de parâmetros do efeito EQ paramétrico (sem dependência de bpy).
Processamento real de áudio acontece no motor C++ — ver chorus.py para
a nota completa sobre a arquitetura.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List

EFFECT_TYPE = "EQ"

BAND_TYPES = ("LOWCUT", "LOWSHELF", "PEAK", "HIGHSHELF", "HIGHCUT")

MAX_BANDS = 6


@dataclass
class EQBand:
    """Uma banda paramétrica do EQ."""

    enabled: bool = True
    band_type: str = "PEAK"     # ver BAND_TYPES
    freq: float = 1000.0        # Hz — 20 a 20000
    gain_db: float = 0.0        # dB — -24 a +24 (ignorado em LOWCUT/HIGHCUT)
    q: float = 0.71             # fator Q / largura da banda

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EQBand":
        valid = {f: data[f] for f in cls.__dataclass_fields__ if f in data}
        return cls(**valid)


@dataclass
class EQParams:
    """Cadeia de bandas do EQ (até MAX_BANDS)."""

    bands: List[EQBand] = field(default_factory=lambda: [
        EQBand(band_type="LOWCUT", freq=80.0, q=0.71, enabled=False),
        EQBand(band_type="PEAK", freq=1000.0, gain_db=0.0, q=1.0, enabled=True),
        EQBand(band_type="HIGHCUT", freq=16000.0, q=0.71, enabled=False),
    ])

    def to_dict(self) -> Dict[str, Any]:
        return {"bands": [b.to_dict() for b in self.bands]}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EQParams":
        bands = [EQBand.from_dict(b) for b in data.get("bands", [])]
        return cls(bands=bands or cls().bands)

    def add_band(self, band_type: str = "PEAK", freq: float = 1000.0) -> EQBand:
        band = EQBand(band_type=band_type, freq=freq)
        if len(self.bands) < MAX_BANDS:
            self.bands.append(band)
        return band


DEFAULT = EQParams()

PRESETS: Dict[str, EQParams] = {
    "Plano": EQParams(),
    "Realce de Voz": EQParams(bands=[
        EQBand(band_type="LOWCUT", freq=100.0, enabled=True),
        EQBand(band_type="PEAK", freq=3000.0, gain_db=3.0, q=1.2, enabled=True),
        EQBand(band_type="HIGHSHELF", freq=8000.0, gain_db=2.0, enabled=True),
    ]),
    "Corte de Grave": EQParams(bands=[
        EQBand(band_type="LOWCUT", freq=200.0, q=0.9, enabled=True),
    ]),
}
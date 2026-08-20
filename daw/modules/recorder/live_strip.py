# modules/recorder/live_strip.py
"""
Strip de gravação AO VIVO: cria a strip assim que a gravação começa e
mantém sua waveform crescendo na timeline conforme o áudio chega, em
vez de só criar/desenhar a strip depois que a gravação já terminou.

Duas peças:

    LiveWavWriter -- escreve o .wav em disco incrementalmente,
        reescrevendo o cabeçalho a cada pedaço novo pra que o arquivo
        seja SEMPRE um WAV válido e completo até aquele ponto (não um
        arquivo truncado/corrompido enquanto grava).

    create_live_strip / refresh_live_strip -- criam a strip no VSE
        assim que a gravação começa, e a "esticam" periodicamente
        recarregando o datablock de Sound do arquivo em disco (o
        Blender cacheia esse datablock por filepath e não detecta
        sozinho que o arquivo cresceu -- por isso o reload explícito).
"""
from __future__ import annotations

import os
import struct
from typing import Optional

import numpy as np

from .utils import bit_depth_to_fmt, encode_pcm, get_sequencer_for_scene, get_strips_collection


class LiveWavWriter:
    """
    Escreve um WAV mono incrementalmente. Cada chamada a `append()`:
      1. Grava o pedaço novo de áudio no final do arquivo.
      2. Reescreve o cabeçalho (RIFF size + data size) refletindo o
         tamanho total já gravado.

    Isso mantém o arquivo sempre abrível como WAV válido a qualquer
    momento durante a gravação -- é o que permite ao Blender carregar
    e mostrar a waveform do que já foi capturado, sem esperar o
    `close()`.
    """
    HEADER_SIZE = 44

    def __init__(self, filepath: str, samplerate: int, bit_depth: str = '24', channels: int = 1):
        self.filepath = filepath
        self.samplerate = int(samplerate)
        self.channels = channels
        self.bit_depth = bit_depth
        self.fmt_tag, self.bits = bit_depth_to_fmt(bit_depth)
        self.block_align = channels * (self.bits // 8)
        self.byte_rate = self.samplerate * self.block_align
        self.total_frames = 0  # amostras por canal já gravadas

        self._fh = open(filepath, 'wb')
        self._write_header(data_size=0)
        self._fh.flush()

    def _write_header(self, data_size: int) -> None:
        self._fh.seek(0)
        self._fh.write(b'RIFF')
        self._fh.write(struct.pack('<I', 36 + data_size))
        self._fh.write(b'WAVE')
        self._fh.write(b'fmt ')
        self._fh.write(struct.pack('<I', 16))
        self._fh.write(struct.pack('<H', self.fmt_tag))
        self._fh.write(struct.pack('<H', self.channels))
        self._fh.write(struct.pack('<I', self.samplerate))
        self._fh.write(struct.pack('<I', self.byte_rate))
        self._fh.write(struct.pack('<H', self.block_align))
        self._fh.write(struct.pack('<H', self.bits))
        self._fh.write(b'data')
        self._fh.write(struct.pack('<I', data_size))

    def append(self, chunk: np.ndarray) -> None:
        """`chunk`: float32 mono em [-1, 1], shape (N,). Não faz nada
        se vazio (silenciosamente -- chamado a cada tick de captura,
        pode legitimamente vir vazio se o dispositivo atrasar)."""
        if chunk is None or chunk.size == 0:
            return
        payload = encode_pcm(chunk, self.bit_depth)
        self._fh.seek(0, os.SEEK_END)
        self._fh.write(payload)
        self.total_frames += chunk.shape[-1]
        data_size = self.total_frames * self.block_align
        self._write_header(data_size)
        # flush() (não fsync) -- suficiente pro Blender ler os bytes
        # atualizados do cache do SO no mesmo processo/máquina; fazer
        # fsync a cada append custaria I/O demais pra uma gravação
        # longa sem trazer benefício aqui (não estamos protegendo
        # contra queda de energia no meio da gravação).
        self._fh.flush()

    @property
    def total_seconds(self) -> float:
        return self.total_frames / float(self.samplerate) if self.samplerate else 0.0

    def close(self) -> None:
        try:
            self._fh.flush()
            self._fh.close()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════
#  STRIP AO VIVO NO VSE
# ═══════════════════════════════════════════════════════════════

def create_live_strip(scene, filepath: str, channel: int, frame_start: int, name: str):
    """
    Cria a strip de gravação assim que a gravação começa (arquivo ainda
    com 0 amostras -- `LiveWavWriter.__init__` já escreveu um cabeçalho
    válido de tamanho 0, então o `bpy.data.sounds.load()` não falha).

    Remove qualquer strip remanescente com o mesmo nome (ex.: sobra de
    uma gravação anterior que travou antes de finalizar).
    """
    seq = get_sequencer_for_scene(scene)
    strips = get_strips_collection(seq)

    existing = strips.get(name)
    if existing is not None:
        try:
            strips.remove(existing)
        except Exception:
            pass

    strip = strips.new_sound(name=name, filepath=filepath, channel=channel, frame_start=frame_start)
    strip.show_waveform = True
    # Duração mínima até o primeiro refresh -- evita strip de duração 0
    # (algumas versões do Blender lidam mal com isso na UI).
    strip.frame_final_end = frame_start + 1
    return strip


def refresh_live_strip(scene, strip_name: str, filepath: str, frame_start: int, total_seconds: float) -> Optional[object]:
    """
    Recarrega o Sound datablock do arquivo (que cresceu desde o último
    refresh) e estica a strip pra cobrir a nova duração -- é isso que
    faz a waveform desenhada na timeline "crescer" enquanto grava.

    O Blender cacheia o datablock de Sound pelo filepath e NÃO detecta
    sozinho que o arquivo em disco mudou -- por isso precisa recarregar
    com `check_existing=False` (força um Sound novo em vez de reusar o
    cacheado) a cada chamada.

    Retorna a strip (ou None se ela não existe mais -- ex.: usuário
    apagou manualmente durante a gravação).
    """
    seq = scene.sequence_editor
    if seq is None:
        return None
    strips = get_strips_collection(seq)
    strip = strips.get(strip_name)
    if strip is None:
        return None

    old_sound = strip.sound
    try:
        import bpy
        new_sound = bpy.data.sounds.load(filepath, check_existing=False)
    except Exception:
        # Arquivo pode estar momentaneamente indisponível pro Blender
        # ler no meio de um write() do LiveWavWriter -- não é fatal,
        # só tenta de novo no próximo refresh.
        return strip

    strip.sound = new_sound
    if old_sound is not None and old_sound.users == 0:
        try:
            import bpy
            bpy.data.sounds.remove(old_sound)
        except Exception:
            pass

    fps = scene.render.fps / max(scene.render.fps_base, 0.0001)
    strip.frame_final_end = frame_start + max(1, round(total_seconds * fps))
    return strip


def remove_live_strip(scene, strip_name: str) -> None:
    """Remove a strip (usado se a gravação for cancelada sem gerar
    áudio útil, ex.: 0 frames capturados)."""
    seq = scene.sequence_editor
    if seq is None:
        return
    strips = get_strips_collection(seq)
    strip = strips.get(strip_name)
    if strip is not None:
        try:
            strips.remove(strip)
        except Exception:
            pass
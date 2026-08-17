# modules/vst/realtime/aud_source.py
"""
!! NÃO TESTADO NESTE AMBIENTE -- precisa de Blender/aud de verdade !!

Este é o ponto de maior risco técnico do plano (ver seção 3 do
documento de arquitetura). A API pública do `aud` (Audaspace) não
expõe um jeito direto de criar uma fonte de áudio "ao vivo" alimentada
por um callback Python arbitrário -- o approach realista é fatiar o
RingBuffer periodicamente em pequenos `aud.Sound.buffer()` e encadeá-los
na sequência, substituindo o pedaço mais à frente do playhead conforme
ele é produzido.

ANTES DE CONFIAR NISSO EM PRODUÇÃO:
    Rode `daw/vst_worker/../modules/vst/realtime/_prototype_aud_swap.py`
    (arquivo separado, ver instruções no final deste módulo) isolado,
    fora do resto do addon, só pra confirmar que trocar o som de uma
    strip durante o playback não causa estalo/glitch perceptível no seu
    Blender. Se causar, a arquitetura muda para bounce automático
    rápido (sem tentar simular stream contínuo) -- ver seção
    "Ordem de implementação recomendada" no documento de arquitetura.
"""
from __future__ import annotations

from typing import Optional

from .ring_buffer import RingBuffer

# Duração de cada fatia trocada na sequência. Menor = transições mais
# frequentes (mais chance de estalo por causa da troca em si) porém
# mais responsivo a invalidação; maior = menos trocas, porém demora
# mais pra uma mudança de automação aparecer no áudio tocando.
SLICE_SECONDS = 0.2


class RingBufferSoundSync:
    """
    Não é uma classe `aud.Sound` de verdade (o `aud` não permite
    subclassificar isso em Python) -- é um objeto auxiliar que o
    PlaybackSupervisor chama periodicamente (a cada tick do timer) pra
    manter uma sequência de SOUND strips curtas sincronizada com o que
    o RingBuffer já tem preenchido, ocupando um canal dedicado do VSE
    (`realtime_channel`) separado dos canais "normais" de strips
    estáticas.

    Fluxo por tick:
        1. Descobre até onde o RingBuffer já está preenchido
           (`ring_buffer.filled_until`).
        2. Se avançou desde o último tick pelo menos `SLICE_SECONDS`,
           extrai esse pedaço novo (`ring_buffer.read(...)`), escreve
           num .wav temporário curto (reaproveita
           `timeline_bridge.write_wav_stereo`) e insere/atualiza uma
           SOUND strip nesse instante exato do canal dedicado.
        3. Remove strips antigas desse canal que já ficaram muito atrás
           do playhead (housekeeping, pra não acumular arquivo/strip
           infinitamente numa sessão de play longa).

    Cada strip criada tem nome determinístico
    (`f"{vst_id}_rt_{slice_index}"`), então re-escrever o mesmo slice
    (depois de uma invalidação) substitui a strip anterior em vez de
    empilhar.
    """

    def __init__(self, scene, vst_id: str, ring_buffer: RingBuffer, channel: int, sample_rate: int = 44100):
        self.scene = scene
        self.vst_id = vst_id
        self.ring_buffer = ring_buffer
        self.channel = channel
        self.sample_rate = sample_rate
        self._last_synced_until = 0.0
        self._tmp_dir: Optional[str] = None

    def tick(self, playhead_seconds: float) -> None:
        # Import tardio -- este módulo só é importado de verdade dentro
        # do Blender, mas o resto do pacote `realtime` precisa continuar
        # importável fora dele (ver ring_buffer.py/prefetch.py, que são
        # testados sem bpy).
        import bpy  # noqa: F401
        from ..timeline_bridge import write_wav_stereo, upsert_sound_strip, beat_to_frame  # noqa: F401
        import tempfile, os

        if self._tmp_dir is None:
            self._tmp_dir = tempfile.mkdtemp(prefix="daw_rt_")

        filled_until = self.ring_buffer.filled_until
        while self._last_synced_until + SLICE_SECONDS <= filled_until:
            slice_start = self._last_synced_until
            slice_index = int(round(slice_start / SLICE_SECONDS))
            n_samples = int(round(SLICE_SECONDS * self.sample_rate))

            audio = self.ring_buffer.read(slice_start, n_samples)

            wav_path = os.path.join(self._tmp_dir, f"{self.vst_id}_rt_{slice_index}.wav")
            write_wav_stereo(wav_path, audio, sample_rate=self.sample_rate)

            fps = self.scene.render.fps / max(self.scene.render.fps_base, 0.0001)
            frame_start = self.scene.frame_start + int(round(slice_start * fps))

            strip_name = f"{self.vst_id}_rt_{slice_index}"
            upsert_sound_strip(self.scene, strip_name, wav_path, self.channel, frame_start)

            self._last_synced_until = slice_start + SLICE_SECONDS

    def cleanup(self) -> None:
        """Remove as strips e arquivos temporários deste canal ao parar o play."""
        import bpy
        from ..timeline_bridge import get_all_strips
        import shutil

        seq = self.scene.sequence_editor
        if seq is not None:
            for s in list(get_all_strips(seq)):
                if s.name.startswith(f"{self.vst_id}_rt_"):
                    try:
                        seq.strips.remove(s)
                    except Exception:
                        try:
                            seq.sequences.remove(s)
                        except Exception:
                            pass

        if self._tmp_dir is not None:
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
            self._tmp_dir = None
        self._last_synced_until = 0.0


# ═══════════════════════════════════════════════════════════════
#  PROTÓTIPO ISOLADO -- rode isto sozinho no Text Editor do Blender
#  (ou como script standalone) ANTES de confiar no resto deste
#  arquivo, pra validar que a troca de strip não estala.
# ═══════════════════════════════════════════════════════════════
_PROTOTYPE_SNIPPET = r'''
# Cole isso no Text Editor do Blender e rode com um projeto de VSE
# aberto, com o cursor tocando (Space). Gera 2 tons diferentes e troca
# entre eles a cada 0.5s no canal 20, pra você OUVIR se a troca estala.
import bpy, tempfile, os, struct, math

def make_tone(path, freq, seconds=0.5, sr=44100):
    n = int(seconds * sr)
    data = bytearray()
    for i in range(n):
        v = int(32767 * 0.3 * math.sin(2 * math.pi * freq * i / sr))
        data += struct.pack('<hh', v, v)  # estéreo
    hdr = struct.pack('<4sI4s4sIHHIIHH4sI', b'RIFF', 36+len(data), b'WAVE',
                       b'fmt ', 16, 1, 2, sr, sr*4, 4, 16, b'data', len(data))
    with open(path, 'wb') as f:
        f.write(hdr); f.write(data)

tmp = tempfile.mkdtemp()
a = os.path.join(tmp, "a.wav"); make_tone(a, 440)
b = os.path.join(tmp, "b.wav"); make_tone(b, 660)

scene = bpy.context.scene
seq = scene.sequence_editor_create()
frame = scene.frame_start
fps = scene.render.fps
for i in range(10):
    path = a if i % 2 == 0 else b
    name = f"proto_{i}"
    try:
        seq.strips.new_sound(name=name, filepath=path, channel=20, frame_start=frame)
    except AttributeError:
        seq.sequences.new_sound(name=name, filepath=path, channel=20, frame_start=frame)
    frame += int(0.5 * fps)

print("Toque a timeline (Space) e ouça o canal 20: se os tons alternarem sem")
print("estalo/glitch na transição, o approach de fatiar em aud.Sound.buffer/")
print("strips curtas é viável. Se estalar, precisa de crossfade de alguns ms")
print("entre as fatias (ajustar write_wav_stereo pra aplicar um fade curto")
print("nas bordas) ou cair pro fallback de bounce automático.")
'''
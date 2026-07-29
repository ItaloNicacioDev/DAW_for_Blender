# modules/recorder/properties.py
"""
Propriedades e estados do módulo Recorder.

[FIX v2] input_device agora é EnumProperty com callback que lê dispositivos
reais do sistema via aud/sounddevice, em vez de StringProperty de texto livre
que nunca mostrava nada útil.
"""
from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
    CollectionProperty,
)
from bpy.types import PropertyGroup


# ═══════════════════════════════════════════════════════════════
#  CALLBACKS DE DISPOSITIVOS  [FIX v2]
# ═══════════════════════════════════════════════════════════════

def _input_device_items(self, context):
    """Callback de items para input_device — lê dispositivos reais."""
    try:
        from .input import get_input_devices
        items = get_input_devices()
        if items:
            return items
    except Exception as e:
        print(f"[DAW Recorder] Erro ao listar entradas: {e}")
    return [('Default', 'Default (Sistema)', 'Dispositivo de entrada padrão')]


def _output_device_items(self, context):
    """Callback de items para output_device — lê dispositivos reais."""
    try:
        from .input import get_output_devices
        items = get_output_devices()
        if items:
            return items
    except Exception as e:
        print(f"[DAW Recorder] Erro ao listar saídas: {e}")
    return [('Default', 'Default (Sistema)', 'Dispositivo de saída padrão')]


class DAW_RecorderTrackArm(PropertyGroup):
    track_index: IntProperty()
    name: StringProperty()


class DAW_RecorderSettings(PropertyGroup):
    bl_idname = "DAW_RecorderSettings"

    is_recording: BoolProperty(
        name="Gravando",
        description="Indica se há uma gravação em andamento",
        default=False,
    )

    is_paused: BoolProperty(
        name="Pausado",
        description="Gravação pausada",
        default=False,
    )

    # [FIX v2] Era StringProperty(default="Default") — campo de texto livre.
    # Agora é EnumProperty com callback que consulta aud/sounddevice
    # toda vez que a UI renderiza o dropdown.
    input_device: EnumProperty(
        name="Dispositivo de Entrada",
        description="Dispositivo de captura de áudio do sistema",
        items=_input_device_items,
    )

    # [FIX v2] Saída também corrigida
    output_device: EnumProperty(
        name="Dispositivo de Saída",
        description="Dispositivo de saída de áudio do sistema",
        items=_output_device_items,
    )

    input_gain_db: FloatProperty(
        name="Ganho (dB)",
        description="Ganho aplicado ao sinal de entrada",
        default=0.0,
        min=-60.0,
        max=24.0,
        step=1.0,
        precision=1,
    )

    monitor_input: BoolProperty(
        name="Monitorar Entrada",
        description="Reproduzir sinal de entrada em tempo real",
        default=False,
    )

    record_format: EnumProperty(
        name="Formato",
        items=[
            ('WAV', "WAV", "Waveform Audio File Format"),
            ('FLAC', "FLAC", "Free Lossless Audio Codec"),
        ],
        default='WAV',
    )

    bit_depth: EnumProperty(
        name="Bits",
        items=[
            ('16', "16-bit", "CD Quality"),
            ('24', "24-bit", "Studio Quality"),
            ('32', "32-bit Float", "Professional"),
        ],
        default='24',
    )

    sample_rate: EnumProperty(
        name="Sample Rate",
        items=[
            ('44100', "44.1 kHz", "CD Standard"),
            ('48000', "48 kHz", "Video Standard"),
            ('96000', "96 kHz", "High Resolution"),
        ],
        default='48000',
    )

    pre_roll_beats: IntProperty(
        name="Pre-roll (beats)",
        default=0,
        min=0,
        max=8,
    )

    count_in_enabled: BoolProperty(
        name="Contagem Regressiva",
        description="Tocar metrônomo antes da gravação",
        default=False,
    )

    punch_in: BoolProperty(
        name="Punch In",
        default=False,
    )

    punch_out: BoolProperty(
        name="Punch Out",
        default=False,
    )

    punch_in_frame: IntProperty(
        name="Início Punch",
        default=0,
        min=0,
    )

    punch_out_frame: IntProperty(
        name="Fim Punch",
        default=0,
        min=0,
    )

    record_start_frame: IntProperty(
        name="Frame de Início",
        default=0,
    )

    record_end_frame: IntProperty(
        name="Frame de Fim",
        default=0,
    )

    current_peak: FloatProperty(
        name="Nível de Pico",
        description="Nível de pico atual do sinal de entrada (0-1)",
        default=0.0,
        min=0.0,
        max=1.0,
    )

    current_rms: FloatProperty(
        name="Nível RMS",
        default=0.0,
        min=0.0,
        max=1.0,
    )

    export_path: StringProperty(
        name="Caminho de Exportação",
        subtype='FILE_PATH',
        default="//recordings/",
    )

    # [FIX v2] Mensagem de status dos dispositivos visível na UI
    device_status: StringProperty(
        name="Status de Dispositivo",
        default="",
    )

    armed_tracks: CollectionProperty(type=DAW_RecorderTrackArm)
    active_arm_index: IntProperty(default=0)


classes = [
    DAW_RecorderTrackArm,
    DAW_RecorderSettings,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.daw_recorder_settings = PointerProperty(type=DAW_RecorderSettings)


def unregister():
    del bpy.types.Scene.daw_recorder_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
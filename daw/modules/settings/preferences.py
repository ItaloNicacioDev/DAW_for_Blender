# modules/settings/preferences.py
"""
Preferências do addon DAW (AddonPreferences do Blender).

Centraliza configurações globais como tema, atalhos padrão, dispositivo de áudio,
e presets de workspace.

[FIX v2] output_device agora é EnumProperty com callback que lê os dispositivos
reais do sistema via aud (e sounddevice se instalado), em vez de StringProperty
de texto livre que nunca mostrava nada.
"""
from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
    PointerProperty,
    CollectionProperty,
)
from bpy.types import AddonPreferences, PropertyGroup


# ═══════════════════════════════════════════════════════════════
#  CALLBACK DE DISPOSITIVOS  [FIX v2]
#
#  EnumProperty com items=callback é a única forma de ter um
#  dropdown que lista dispositivos reais em tempo real no Blender.
#  O callback é chamado toda vez que a UI renderiza o campo.
# ═══════════════════════════════════════════════════════════════

def _output_device_items(self, context):
    """Callback de items para output_device EnumProperty."""
    try:
        from ..recorder.input import get_output_devices
        items = get_output_devices()
        if items:
            return items
    except Exception as e:
        print(f"[DAW Prefs] Erro ao listar saídas: {e}")
    return [('Default', 'Default (Sistema)', 'Dispositivo de saída padrão do sistema')]


def _input_device_items(self, context):
    """Callback de items para input_device EnumProperty."""
    try:
        from ..recorder.input import get_input_devices
        items = get_input_devices()
        if items:
            return items
    except Exception as e:
        print(f"[DAW Prefs] Erro ao listar entradas: {e}")
    return [('Default', 'Default (Sistema)', 'Dispositivo de entrada padrão do sistema')]


class DAW_PresetKeymap(PropertyGroup):
    """Define um preset de keymap para quick-load."""
    name: StringProperty(name="Nome", default="Preset 1")
    description: StringProperty(name="Descrição", default="")


class DAW_PreferencesAudio(PropertyGroup):
    """Preferências de áudio."""

    # [FIX v2] Era StringProperty(default="Default") — campo de texto livre
    # que nunca listava dispositivos reais. Agora é EnumProperty com callback
    # que consulta aud/sounddevice a cada renderização da UI.
    output_device: EnumProperty(
        name="Dispositivo de Saída",
        description="Dispositivo de áudio de saída do sistema",
        items=_output_device_items,
    )

    # [FIX v2] Mesmo problema: input como StringProperty livre → EnumProperty
    input_device: EnumProperty(
        name="Dispositivo de Entrada",
        description="Dispositivo de captura de áudio do sistema",
        items=_input_device_items,
    )

    samplerate: IntProperty(
        name="Sample Rate",
        description="Taxa de amostragem em Hz",
        default=48000, min=22050, max=192000,
    )
    buffer_size: IntProperty(
        name="Tamanho do Buffer",
        description="Tamanho do buffer de áudio (frames)",
        default=512, min=64, max=4096,
    )
    enable_dither: BoolProperty(
        name="Ativar Dither",
        description="Aplica dither ao mixdown (reduz artefatos de quantização)",
        default=False
    )


class DAW_PreferencesUI(PropertyGroup):
    """Preferências de interface."""
    theme: EnumProperty(
        name="Tema",
        description="Tema visual do addon",
        items=[
            ('DARK', "Escuro", "Tema escuro com neon"),
            ('LIGHT', "Claro", "Tema claro minimalista"),
            ('BLENDER', "Blender Padrão", "Usa cores padrão do Blender"),
        ],
        default='DARK',
    )

    font_scale: FloatProperty(
        name="Escala de Fonte",
        description="Escala relativa da fonte na UI",
        default=1.0, min=0.8, max=1.5, step=0.05,
    )

    panel_width: IntProperty(
        name="Largura Padrão (px)",
        description="Largura sugerida dos painéis",
        default=300, min=200, max=600,
    )

    show_tooltips: BoolProperty(
        name="Mostrar Tooltips",
        description="Exibe tooltips flutuantes",
        default=True
    )

    show_playhead_indicator: BoolProperty(
        name="Indicador de Playhead",
        description="Mostra posição atual de reprodução",
        default=True
    )


class DAW_PreferencesWorkspace(PropertyGroup):
    """Preferências de workspace."""
    auto_layout: BoolProperty(
        name="Layout Automático",
        description="Reorganiza painéis automaticamente",
        default=True
    )

    remember_last_project: BoolProperty(
        name="Lembrar Último Projeto",
        description="Reabre o último projeto ao iniciar",
        default=True
    )

    autosave_interval: IntProperty(
        name="Auto-Save (minutos)",
        description="Intervalo de auto-save (0 = desativado)",
        default=5, min=0, max=60,
    )


class DAW_PreferencesKeymaps(PropertyGroup):
    """Gerenciador de presets de keymaps."""
    presets: CollectionProperty(type=DAW_PresetKeymap)
    active_preset_index: IntProperty(default=0)

    play_pause: StringProperty(
        name="Play/Pause",
        description="Atalho para play/pause (ex: 'SPACE')",
        default="SPACE"
    )
    stop: StringProperty(
        name="Stop",
        default="SHIFT SPACE"
    )
    record: StringProperty(
        name="Record",
        default="CTRL R"
    )
    undo: StringProperty(
        name="Undo",
        default="CTRL Z"
    )
    redo: StringProperty(
        name="Redo",
        default="CTRL SHIFT Z"
    )


class DAW_Preferences(AddonPreferences):
    """Addon Preferences do DAW."""
    bl_idname = __package__.split('.')[0] if '.' in __package__ else 'daw'

    # Sub-groups
    audio: PointerProperty(type=DAW_PreferencesAudio)
    ui: PointerProperty(type=DAW_PreferencesUI)
    workspace: PointerProperty(type=DAW_PreferencesWorkspace)
    keymaps: PointerProperty(type=DAW_PreferencesKeymaps)

    # Geral
    debug_mode: BoolProperty(
        name="Modo Debug",
        description="Ativa logs detalhados no console",
        default=False
    )

    check_for_updates: BoolProperty(
        name="Verificar Atualizações",
        description="Verifica nova versão ao iniciar",
        default=True
    )

    reset_on_start: BoolProperty(
        name="Resetar ao Iniciar",
        description="Reseta configurações para padrões ao abrir Blender",
        default=False
    )

    def draw(self, context):
        layout = self.layout

        # Áudio
        box = layout.box()
        box.label(text="Áudio", icon='SPEAKER')
        row = box.row(align=True)
        row.prop(self.audio, "output_device", text="Saída")
        row.operator("daw.test_output_device", text="", icon='PLAY_SOUND')
        box.prop(self.audio, "input_device",  text="Entrada")
        row = box.row(align=True)
        row.prop(self.audio, "samplerate",  text="Sample Rate")
        row.prop(self.audio, "buffer_size", text="Buffer")
        box.prop(self.audio, "enable_dither")

        # [FIX v3] Diagnóstico de dispositivo/driver: avisa quando não há
        # sounddevice instalado (lista de dispositivos limitada) ou
        # quando não há nenhum host API ASIO disponível no sistema --
        # útil pra interfaces externas (ex.: TEYUN) que só aparecem
        # corretamente, ou com baixa latência, com um driver ASIO
        # instalado. Ver modules/recorder/input.py::get_audio_diagnostics().
        try:
            from ..recorder.input import get_audio_diagnostics
            diag = get_audio_diagnostics()
            if diag["recommendation"]:
                warn_box = box.box()
                col = warn_box.column(align=True)
                col.label(text="Dispositivo não aparece ou latência alta?", icon='ERROR')
                for line in diag["recommendation"].split("\n"):
                    line = line.strip()
                    if line:
                        col.label(text=line)
                row_links = warn_box.row(align=True)
                op1 = row_links.operator("wm.url_open", text="ASIO4ALL", icon='URL')
                op1.url = "https://asio4all.org"
                op2 = row_links.operator("wm.url_open", text="FlexASIO", icon='URL')
                op2.url = "https://github.com/dechamps/FlexASIO"
            elif diag["has_asio_hostapi"]:
                asio_names = [h for h in diag["hostapis"] if "ASIO" in h.upper()]
                box.label(text=f"Driver ASIO detectado: {', '.join(asio_names)}", icon='CHECKMARK')
        except Exception as e:
            box.label(text=f"Diagnóstico de áudio indisponível: {e}", icon='ERROR')

        # UI
        box2 = layout.box()
        box2.label(text="Interface", icon='PREFERENCES')
        box2.prop(self.ui, "theme")
        box2.prop(self.ui, "font_scale")
        box2.prop(self.ui, "show_tooltips")
        box2.prop(self.ui, "show_playhead_indicator")

        # Workspace
        box3 = layout.box()
        box3.label(text="Workspace", icon='WORKSPACE')
        box3.prop(self.workspace, "auto_layout")
        box3.prop(self.workspace, "remember_last_project")
        box3.prop(self.workspace, "autosave_interval")

        # Geral
        layout.prop(self, "debug_mode")
        layout.prop(self, "check_for_updates")

        # Atualizações (verificação/instalação a partir do GitHub)
        try:
            from ..update.ui import draw_updater_compact
            box_upd = layout.box()
            draw_updater_compact(box_upd, context)
        except Exception as e:
            layout.label(text=f"Updater indisponível: {e}", icon='ERROR')


classes = [
    DAW_PresetKeymap,
    DAW_PreferencesAudio,
    DAW_PreferencesUI,
    DAW_PreferencesWorkspace,
    DAW_PreferencesKeymaps,
    DAW_Preferences,
]


def get_preferences() -> DAW_Preferences:
    """Função helper para acessar preferências do addon."""
    return bpy.context.preferences.addons[
        __package__.split('.')[0] if '.' in __package__ else 'daw'
    ].preferences


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
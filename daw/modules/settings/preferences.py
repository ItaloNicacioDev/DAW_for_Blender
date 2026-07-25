# modules/settings/preferences.py
"""
Preferências do addon DAW (AddonPreferences do Blender).

Centraliza configurações globais como tema, atalhos padrão, dispositivo de áudio,
e presets de workspace.
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


class DAW_PresetKeymap(PropertyGroup):
    """Define um preset de keymap para quick-load."""
    name: StringProperty(name="Nome", default="Preset 1")
    description: StringProperty(name="Descrição", default="")


class DAW_PreferencesAudio(PropertyGroup):
    """Preferências de áudio."""
    output_device: StringProperty(
        name="Dispositivo de Saída",
        description="Nome do dispositivo de áudio de saída (Default se vazio)",
        default="Default"
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
    
    # Atalhos padrão
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
    return bpy.context.preferences.addons[__package__.split('.')[0] if '.' in __package__ else 'daw'].preferences


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
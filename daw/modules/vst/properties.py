# modules/vst/properties.py
"""
PropertyGroups do Blender para VST.

Melhorias em relação à versão anterior:
    - DawVstSettings: novos campos
        · auto_bounce_on_change  — bounce automático ao mudar parâmetro
        · param_display_limit    — quantos parâmetros mostrar por vez (scroll)
        · is_live_monitoring     — estado do monitor ao vivo
        · is_installing_sounddevice / sounddevice_install_log
    - DawVstProperty: novo campo
        · param_scroll_offset    — para scroll de parâmetros na UI
        · param_search           — busca por nome de parâmetro
    - DawVstChainProperty: sem alteração estrutural, mas mantido limpo
"""
from __future__ import annotations

import bpy
from bpy.props import (
    StringProperty,
    FloatProperty,
    BoolProperty,
    IntProperty,
    CollectionProperty,
    PointerProperty,
    EnumProperty,
)


class DawVstParameterProperty(bpy.types.PropertyGroup):
    """Representa um parâmetro de VST na UI"""

    param_id: IntProperty(
        name="Parameter ID",
        description="ID único do parâmetro",
        default=0,
        min=0,
    )

    param_name: StringProperty(
        name="Parameter Name",
        description="Nome do parâmetro",
        default="",
    )

    param_value: FloatProperty(
        name="Value",
        description="Valor normalizado (0.0 - 1.0)",
        default=0.5,
        min=0.0,
        max=1.0,
    )

    param_label: StringProperty(
        name="Label",
        description="Unidade/label do parâmetro",
        default="",
    )

    is_automatable: BoolProperty(
        name="Automatable",
        description="Pode ser automatizado",
        default=True,
    )


class DawVstProperty(bpy.types.PropertyGroup):
    """Representa um VST carregado"""

    vst_path: StringProperty(
        name="VST Path",
        description="Caminho absoluto do arquivo VST",
        default="",
        subtype="FILE_PATH",
    )

    vst_name: StringProperty(
        name="VST Name",
        description="Nome de exibição do VST",
        default="",
    )

    vst_id: StringProperty(
        name="VST ID",
        description="ID único do VST (para referência)",
        default="",
    )

    vst_type: EnumProperty(
        name="VST Type",
        description="Tipo de VST",
        items=[
            ("EFFECT", "Effect", "VST effect (processamento de áudio)"),
            ("INSTRUMENT", "Instrument", "VST instrument (síntese/sampling)"),
        ],
        default="EFFECT",
    )

    bypass: BoolProperty(
        name="Bypass",
        description="Desabilita processamento do VST",
        default=False,
    )

    volume: FloatProperty(
        name="Volume",
        description="Ganho de saída",
        default=0.0,
        min=-96.0,
        max=6.0,
        unit="POWER",
    )

    is_loaded: BoolProperty(
        name="Loaded",
        description="VST foi carregado com sucesso",
        default=False,
    )

    error_message: StringProperty(
        name="Error",
        description="Mensagem de erro ao carregar",
        default="",
    )

    # Parâmetros do VST
    parameters: CollectionProperty(
        type=DawVstParameterProperty,
        name="Parameters",
        description="Parâmetros do VST",
    )

    # Preset atual
    current_preset: StringProperty(
        name="Current Preset",
        description="Nome do preset carregado",
        default="default",
    )

    # ── Scroll e busca de parâmetros ──────────────────────────────────
    param_scroll_offset: IntProperty(
        name="Scroll de Parâmetros",
        description="Índice do primeiro parâmetro visível (para scroll quando há muitos)",
        default=0,
        min=0,
    )

    param_search: StringProperty(
        name="Buscar Parâmetro",
        description="Filtra parâmetros por nome",
        default="",
    )

    # Expandido ou recolhido na UI
    is_expanded: BoolProperty(
        name="Expandido",
        description="Mostra detalhes (parâmetros, presets) deste VST",
        default=True,
    )


class DawVstChainProperty(bpy.types.PropertyGroup):
    """Representa uma cadeia de VST effects"""

    chain_id: StringProperty(
        name="Chain ID",
        description="ID único da cadeia",
        default="",
    )

    vsts: CollectionProperty(
        type=DawVstProperty,
        name="VSTs",
        description="VSTs na cadeia",
    )

    active_vst_index: IntProperty(
        name="Active VST Index",
        description="Índice do VST ativo",
        default=0,
        min=0,
    )

    max_slots: IntProperty(
        name="Max Slots",
        description="Número máximo de slots",
        default=10,
        min=1,
        max=64,
    )


class DawVstRackProperty(bpy.types.PropertyGroup):
    """Representa um rack de VST instruments"""

    instruments: CollectionProperty(
        type=DawVstProperty,
        name="Instruments",
        description="Instrumentos VST carregados",
    )

    active_channel: IntProperty(
        name="Active Channel",
        description="Channel ativo (índice)",
        default=0,
        min=0,
        max=15,
    )


class DawVstBrowserProperty(bpy.types.PropertyGroup):
    """UI de navegação/seleção de VSTs"""

    vst_directory: StringProperty(
        name="VST Directory",
        description="Diretório padrão de VSTs",
        default="",
        subtype="DIR_PATH",
    )

    filter_type: EnumProperty(
        name="Filter Type",
        items=[
            ("ALL", "All", "Mostrar todos"),
            ("EFFECT", "Effects", "Apenas effects"),
            ("INSTRUMENT", "Instruments", "Apenas instruments"),
        ],
        default="ALL",
    )

    search_term: StringProperty(
        name="Search",
        description="Buscar VST por nome",
        default="",
    )

    discovered_vsts: CollectionProperty(
        type=DawVstProperty,
        name="Discovered VSTs",
    )

    is_scanning: BoolProperty(
        name="Is Scanning",
        description="Escaneando diretório",
        default=False,
    )


class DawVstSettings(bpy.types.PropertyGroup):
    """Configurações globais de VST"""

    vst_directories: StringProperty(
        name="VST Directories",
        description="Diretórios onde procurar VSTs (separados por ;)",
        default="",
    )

    auto_scan_on_startup: BoolProperty(
        name="Auto-scan on Startup",
        description="Escanear VSTs ao iniciar",
        default=True,
    )

    enable_vst_effects: BoolProperty(
        name="Enable VST Effects",
        description="Ativar processamento de efeitos",
        default=True,
    )

    enable_vst_instruments: BoolProperty(
        name="Enable VST Instruments",
        description="Ativar síntese via instrumentos",
        default=True,
    )

    max_effect_slots_per_track: IntProperty(
        name="Max Effect Slots",
        description="Máximo de efeitos por track",
        default=10,
        min=1,
        max=64,
    )

    max_instruments: IntProperty(
        name="Max Instruments",
        description="Máximo de instrumentos simultâneos",
        default=16,
        min=1,
        max=64,
    )

    # ── Auto-bounce ───────────────────────────────────────────────────
    auto_bounce_on_change: BoolProperty(
        name="Auto-Bounce ao Mudar Parâmetro",
        description=(
            "Re-renderiza automaticamente o instrumento VST na timeline "
            "após mudar um parâmetro (debounce de 0.8s). "
            "Desative se a re-renderização estiver lenta."
        ),
        default=False,
    )

    # ── Monitor ao vivo ──────────────────────────────────────────────
    is_live_monitoring: BoolProperty(
        name="Monitor Ao Vivo Ativo",
        description="Efeitos VST estão processando o microfone em tempo real",
        default=False,
    )

    # ── Instalação do dawdreamer ──────────────────────────────────────
    is_installing_dawdreamer: BoolProperty(
        name="Instalando dawdreamer",
        description="Instalação do dawdreamer em andamento",
        default=False,
    )

    dawdreamer_install_log: StringProperty(
        name="Log da Instalação",
        description="Últimas linhas de saída da instalação do dawdreamer",
        default="",
    )

    # ── Instalação do sounddevice ─────────────────────────────────────
    is_installing_sounddevice: BoolProperty(
        name="Instalando sounddevice",
        description="Instalação do sounddevice em andamento",
        default=False,
    )

    sounddevice_install_log: StringProperty(
        name="Log sounddevice",
        description="Últimas linhas de saída da instalação do sounddevice",
        default="",
    )

    # ── UI de parâmetros ─────────────────────────────────────────────
    param_display_limit: IntProperty(
        name="Parâmetros por Página",
        description="Quantos parâmetros mostrar por vez (use scroll para ver mais)",
        default=12,
        min=4,
        max=64,
    )


# ═══════════════════════════════════════════════════════════════
#  REGISTRO NO BLENDER
# ═══════════════════════════════════════════════════════════════

_PROP_CLASSES = [
    DawVstParameterProperty,
    DawVstProperty,
    DawVstChainProperty,
    DawVstRackProperty,
    DawVstBrowserProperty,
    DawVstSettings,
]


def register():
    for cls in _PROP_CLASSES:
        bpy.utils.register_class(cls)

    bpy.types.Scene.daw_vst = PointerProperty(
        type=DawVstSettings,
        name="DAW VST Settings",
        description="Configurações e state de VST",
    )

    bpy.types.Scene.daw_vst_chains = CollectionProperty(
        type=DawVstChainProperty,
        name="DAW VST Chains",
        description="Cadeias de efeitos por channel",
    )

    bpy.types.Scene.daw_vst_instruments = PointerProperty(
        type=DawVstRackProperty,
        name="DAW VST Instruments",
        description="Rack de instrumentos VST",
    )

    bpy.types.Scene.daw_vst_browser = PointerProperty(
        type=DawVstBrowserProperty,
        name="DAW VST Browser",
        description="Estado do navegador de VST",
    )


def unregister():
    if hasattr(bpy.types.Scene, "daw_vst"):
        del bpy.types.Scene.daw_vst
    if hasattr(bpy.types.Scene, "daw_vst_chains"):
        del bpy.types.Scene.daw_vst_chains
    if hasattr(bpy.types.Scene, "daw_vst_instruments"):
        del bpy.types.Scene.daw_vst_instruments
    if hasattr(bpy.types.Scene, "daw_vst_browser"):
        del bpy.types.Scene.daw_vst_browser

    for cls in reversed(_PROP_CLASSES):
        bpy.utils.unregister_class(cls)
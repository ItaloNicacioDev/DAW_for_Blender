# modules/vst/propertygroups.py - ARQUIVO NOVO
# ============================================================================
# Define todos os PropertyGroups RNA necessários para o módulo VST
# Deve ser importado e registrado em vst/register.py
# ============================================================================

from __future__ import annotations

import bpy
from bpy.props import (
    StringProperty, FloatProperty, IntProperty, BoolProperty,
    CollectionProperty, PointerProperty, EnumProperty
)
from bpy.types import PropertyGroup, Scene


# ═══════════════════════════════════════════════════════════════
#  PARÂMETRO DE VST (campo escalar)
# ═══════════════════════════════════════════════════════════════

class DawVstParameter(PropertyGroup):
    """Representa um parâmetro de um plugin VST"""
    param_id: IntProperty(
        name="Parameter ID",
        description="ID do parâmetro no plugin VST",
        default=0,
        min=0,
    )
    param_name: StringProperty(
        name="Parameter Name",
        description="Nome humano do parâmetro",
        default="Param",
    )
    param_value: FloatProperty(
        name="Value",
        description="Valor normalizado (0.0-1.0)",
        default=0.5,
        min=0.0,
        max=1.0,
    )
    param_label: StringProperty(
        name="Label",
        description="Label/unidade do parâmetro (ex: 'dB', 'Hz')",
        default="",
    )


# ═══════════════════════════════════════════════════════════════
#  ITEM DE VST (efeito ou instrumento em uma cadeia)
# ═══════════════════════════════════════════════════════════════

class DawVstProperty(PropertyGroup):
    """Propriedade de um plugin VST (effect ou instrument)"""
    
    vst_id: StringProperty(
        name="VST ID",
        description="ID único do VST (ex: 'serum_01')",
        default="",
    )
    vst_path: StringProperty(
        name="VST Path",
        description="Caminho completo para o plugin (.dll, .vst3, etc)",
        default="",
        subtype='FILE_PATH',
    )
    vst_name: StringProperty(
        name="VST Name",
        description="Nome legível do plugin (ex: 'Serum')",
        default="Untitled VST",
    )
    
    # VST2 vs VST3
    vst_type: EnumProperty(
        name="VST Type",
        description="Tipo de plugin",
        items=[
            ('EFFECT', 'Effect', 'Audio effect plugin'),
            ('INSTRUMENT', 'Instrument', 'Synthesizer plugin'),
        ],
        default='EFFECT',
    )
    
    # Estado da cadeia
    bypass: BoolProperty(
        name="Bypass",
        description="Bypass deste VST",
        default=False,
    )
    is_loaded: BoolProperty(
        name="Is Loaded",
        description="True se o plugin foi carregado com sucesso",
        default=False,
    )
    error_message: StringProperty(
        name="Error Message",
        description="Mensagem de erro se o carregamento falhar",
        default="",
    )
    
    # Presets
    current_preset: StringProperty(
        name="Current Preset",
        description="Nome do preset ativo",
        default="default",
    )
    
    # Parâmetros
    parameters: CollectionProperty(
        type=DawVstParameter,
        name="Parameters",
        description="Lista de parâmetros do VST",
    )


# ═══════════════════════════════════════════════════════════════
#  CADEIA DE EFEITOS (VST effect chain)
# ═══════════════════════════════════════════════════════════════

class DawVstChain(PropertyGroup):
    """Uma cadeia de efeitos VST para um canal/faixa"""
    
    chain_id: IntProperty(
        name="Chain ID",
        description="ID da cadeia (indexação em tracks)",
        default=0,
        min=0,
    )
    name: StringProperty(
        name="Chain Name",
        description="Nome da cadeia",
        default="Effect Chain",
    )
    
    # VSTs nesta cadeia
    vsts: CollectionProperty(
        type=DawVstProperty,
        name="VSTs",
        description="Plugins VST nesta cadeia de efeitos",
    )
    active_vst_index: IntProperty(
        name="Active VST Index",
        description="Índice do VST selecionado",
        default=0,
        min=0,
    )
    
    def active_vst(self):
        """Retorna o VST ativo, ou None"""
        if 0 <= self.active_vst_index < len(self.vsts):
            return self.vsts[self.active_vst_index]
        return None


# ═══════════════════════════════════════════════════════════════
#  RACK DE INSTRUMENTOS VST
# ═══════════════════════════════════════════════════════════════

class DawVstInstrumentRack(PropertyGroup):
    """Rack de instrumentos VST (sintetizadores/samplers)"""
    
    instruments: CollectionProperty(
        type=DawVstProperty,
        name="Instruments",
        description="Plugins VST que são instrumentos",
    )
    active_instrument_index: IntProperty(
        name="Active Instrument Index",
        description="Índice do instrumento selecionado",
        default=0,
        min=0,
    )
    
    def active_instrument(self):
        """Retorna o instrumento ativo, ou None"""
        if 0 <= self.active_instrument_index < len(self.instruments):
            return self.instruments[self.active_instrument_index]
        return None


# ═══════════════════════════════════════════════════════════════
#  CONFIGURAÇÕES GLOBAIS VST
# ═══════════════════════════════════════════════════════════════

class DawVstSettings(PropertyGroup):
    """Configurações globais do módulo VST"""
    
    vst_directories: StringProperty(
        name="VST Directories",
        description="Diretórios onde buscar plugins (separados por ;)",
        default="",
    )
    
    auto_bounce_on_change: BoolProperty(
        name="Auto Bounce on Change",
        description="Fazer bounce automático ao mudar parâmetros do VST",
        default=False,
    )
    
    param_display_limit: IntProperty(
        name="Parameter Display Limit",
        description="Número máximo de parâmetros para exibir na UI",
        default=12,
        min=1,
        max=100,
    )
    
    max_effect_slots_per_track: IntProperty(
        name="Max Effect Slots Per Track",
        description="Número máximo de efeitos por faixa",
        default=10,
        min=1,
        max=32,
    )
    
    max_instruments: IntProperty(
        name="Max Instruments",
        description="Número máximo de instrumentos no rack",
        default=16,
        min=1,
        max=64,
    )
    
    # Monitor ao vivo (para o live_monitor.py)
    live_monitor_enabled: BoolProperty(
        name="Live Monitor Enabled",
        description="Ativar monitor de áudio ao vivo (mic -> VST efeito -> saída)",
        default=False,
    )
    live_monitor_input_device: StringProperty(
        name="Live Monitor Input Device",
        description="Dispositivo de entrada de áudio",
        default="default",
    )
    live_monitor_output_device: StringProperty(
        name="Live Monitor Output Device",
        description="Dispositivo de saída de áudio",
        default="default",
    )


# ═══════════════════════════════════════════════════════════════
#  REGISTRO (chamar em vst/register.py)
# ═══════════════════════════════════════════════════════════════

def register_propertygroups():
    """Registra todos os PropertyGroups de VST"""
    bpy.utils.register_class(DawVstParameter)
    bpy.utils.register_class(DawVstProperty)
    bpy.utils.register_class(DawVstChain)
    bpy.utils.register_class(DawVstInstrumentRack)
    bpy.utils.register_class(DawVstSettings)
    
    # Adicionar às propriedades da Scene
    Scene.daw_vst = PointerProperty(
        type=DawVstSettings,
        name="DAW VST Settings",
        description="Configurações globais do módulo VST",
    )
    Scene.daw_vst_chains = CollectionProperty(
        type=DawVstChain,
        name="DAW VST Chains",
        description="Cadeias de efeitos VST por canal",
    )
    Scene.daw_vst_instruments = PointerProperty(
        type=DawVstInstrumentRack,
        name="DAW VST Instruments",
        description="Rack de instrumentos VST",
    )


def unregister_propertygroups():
    """Desregistra todos os PropertyGroups de VST"""
    # Remover propriedades da Scene
    if hasattr(Scene, "daw_vst"):
        del Scene.daw_vst
    if hasattr(Scene, "daw_vst_chains"):
        del Scene.daw_vst_chains
    if hasattr(Scene, "daw_vst_instruments"):
        del Scene.daw_vst_instruments
    
    # Desregistrar classes (ordem inversa)
    bpy.utils.unregister_class(DawVstSettings)
    bpy.utils.unregister_class(DawVstInstrumentRack)
    bpy.utils.unregister_class(DawVstChain)
    bpy.utils.unregister_class(DawVstProperty)
    bpy.utils.unregister_class(DawVstParameter)
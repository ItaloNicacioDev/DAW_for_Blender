# modules/vst/ui.py
"""
Painéis de UI do Blender para o módulo VST.

Três painéis:
    - DAW_PT_VstBrowser    -> configurar diretórios, escanear, listar
                              plugins encontrados e adicioná-los.
    - DAW_PT_VstEffects    -> cadeia de efeitos VST do canal ativo.
    - DAW_PT_VstInstruments-> rack de instrumentos VST (síntese MIDI).

Segue o mesmo padrão dos outros painéis do projeto:
    bl_space_type = 'SEQUENCE_EDITOR', bl_category = "DAW".
"""
from __future__ import annotations

import bpy
from bpy.types import Panel, UIList

from . import engine
from .utils import get_or_create_chain


def _active_channel_index(context) -> int:
    rack_props = getattr(context.scene, "daw_channel_rack", None)
    if rack_props is not None:
        return rack_props.active_channel_index
    return 0


def _active_channel_name(context) -> str:
    rack_props = getattr(context.scene, "daw_channel_rack", None)
    if rack_props is not None and 0 <= rack_props.active_channel_index < len(rack_props.channels):
        return rack_props.channels[rack_props.active_channel_index].name
    return "Canal 0"


def _draw_engine_status(layout):
    """Aviso + botão de instalação quando dawdreamer não está disponível."""
    settings = bpy.context.scene.daw_vst
    if engine.is_available():
        return

    box = layout.box()
    box.label(text="Motor VST (dawdreamer) indisponível", icon='ERROR')
    if settings.is_installing_dawdreamer:
        box.label(text="Instalando... veja o Console do Sistema", icon='SORTTIME')
    else:
        box.operator("daw.install_dawdreamer", icon='IMPORT')
    if settings.dawdreamer_install_log:
        col = box.column(align=True)
        for line in settings.dawdreamer_install_log.splitlines()[-4:]:
            col.label(text=line)


def _draw_vst_item(layout, item, is_instrument: bool, channel_index: int, index: int):
    """Bloco de detalhe (parâmetros, bypass, presets) de um VST carregado."""
    box = layout.box()
    row = box.row(align=True)
    icon = 'CHECKMARK' if item.is_loaded else 'ERROR'
    row.label(text=item.vst_name or "(sem nome)", icon=icon)
    row.prop(item, "bypass", text="", icon='HIDE_ON' if item.bypass else 'HIDE_OFF', emboss=False)

    if item.error_message:
        box.label(text=item.error_message, icon='INFO')

    row = box.row(align=True)
    op = row.operator("daw.reload_vst", text="Recarregar", icon='FILE_REFRESH')
    op.channel_index = channel_index
    op.vst_index = index
    op.is_instrument = is_instrument

    if len(item.parameters):
        col = box.column(align=True)
        for p in item.parameters:
            row = col.row(align=True)
            row.prop(p, "param_value", text=p.param_name)
            op = row.operator("daw.set_vst_parameter", text="", icon='CHECKMARK')
            op.vst_id = item.vst_id
            op.param_id = p.param_id
            op.value = p.param_value

    preset_row = box.row(align=True)
    op = preset_row.operator("daw.save_vst_preset", text="Salvar Preset", icon='FILE_TICK')
    op.vst_id = item.vst_id
    op = preset_row.operator("daw.load_vst_preset", text="Padrão", icon='LOOP_BACK')
    op.vst_id = item.vst_id
    op.preset_name = "default"


# ---------------------------------------------------------------------- #
# Browser de VSTs
# ---------------------------------------------------------------------- #
class DAW_UL_DiscoveredVstList(UIList):
    bl_idname = "DAW_UL_discovered_vst_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.label(text=item.vst_name, icon='PLUGIN')
        op = row.operator("daw.add_vst_effect", text="", icon='SEQ_STRIP_DUPLICATE')
        op.vst_path = item.vst_path
        op.vst_name = item.vst_name
        op = row.operator("daw.add_vst_instrument", text="", icon='OUTLINER_OB_SPEAKER')
        op.vst_path = item.vst_path
        op.vst_name = item.vst_name


class DAW_PT_VstBrowser(Panel):
    bl_label = "VST Browser"
    bl_idname = "DAW_PT_vst_browser"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_order = 4

    def draw(self, context):
        layout = self.layout
        _draw_engine_status(layout)

        settings = context.scene.daw_vst
        browser = context.scene.daw_vst_browser

        col = layout.column(align=True)
        col.prop(settings, "vst_directories", text="Pastas")
        row = col.row(align=True)
        row.operator("daw.pick_vst_directory", text="Adicionar Pasta", icon='FILE_FOLDER')
        row.operator(
            "daw.scan_vst_directories", text="Escanear",
            icon='VIEWZOOM' if not browser.is_scanning else 'SORTTIME',
        )

        layout.prop(browser, "search_term", text="", icon='VIEWZOOM')

        term = browser.search_term.lower().strip()
        visible = [
            (i, v) for i, v in enumerate(browser.discovered_vsts)
            if not term or term in v.vst_name.lower()
        ]

        if not visible:
            layout.label(text="Nenhum VST encontrado. Configure as pastas e escaneie.", icon='INFO')
            return

        box = layout.box()
        for i, v in visible:
            row = box.row(align=True)
            row.label(text=v.vst_name, icon='PLUGIN')
            op = row.operator("daw.add_vst_effect", text="Efeito", icon='SEQ_STRIP_DUPLICATE')
            op.vst_path = v.vst_path
            op.vst_name = v.vst_name
            op = row.operator("daw.add_vst_instrument", text="Instrumento", icon='OUTLINER_OB_SPEAKER')
            op.vst_path = v.vst_path
            op.vst_name = v.vst_name


# ---------------------------------------------------------------------- #
# Cadeia de efeitos VST (por canal)
# ---------------------------------------------------------------------- #
class DAW_PT_VstEffects(Panel):
    bl_label = "VST (Efeitos)"
    bl_idname = "DAW_PT_vst_effects"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_order = 5

    def draw(self, context):
        layout = self.layout
        _draw_engine_status(layout)

        channel_index = _active_channel_index(context)
        chain = get_or_create_chain(context.scene, channel_index)

        layout.label(text=f"Canal: {_active_channel_name(context)}", icon='SEQ_STRIP_DUPLICATE')

        if not len(chain.vsts):
            layout.label(text="Nenhum VST de efeito neste canal.", icon='INFO')
            return

        for index, item in enumerate(chain.vsts):
            _draw_vst_item(layout, item, is_instrument=False, channel_index=channel_index, index=index)
            op = layout.operator("daw.remove_vst_effect", text="Remover", icon='TRASH')
            op.channel_index = channel_index
            op.vst_index = index


# ---------------------------------------------------------------------- #
# Rack de instrumentos VST
# ---------------------------------------------------------------------- #
class DAW_PT_VstInstruments(Panel):
    bl_label = "VST (Instrumentos)"
    bl_idname = "DAW_PT_vst_instruments"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "DAW"
    bl_order = 6

    def draw(self, context):
        layout = self.layout
        _draw_engine_status(layout)

        rack = context.scene.daw_vst_instruments

        if not len(rack.instruments):
            layout.label(text="Nenhum instrumento VST carregado.", icon='INFO')
            return

        for index, item in enumerate(rack.instruments):
            _draw_vst_item(layout, item, is_instrument=True, channel_index=-1, index=index)
            op = layout.operator("daw.remove_vst_instrument", text="Remover", icon='TRASH')
            op.vst_index = index


classes = [
    DAW_UL_DiscoveredVstList,
    DAW_PT_VstBrowser,
    DAW_PT_VstEffects,
    DAW_PT_VstInstruments,
]
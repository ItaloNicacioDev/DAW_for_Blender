# modules/vst/ui.py
"""
Painéis de UI do Blender para o módulo VST.

Melhorias em relação à versão anterior:
    - Parâmetros com scroll e busca por nome (não lista tudo de uma vez)
    - Botões Up/Down para reordenar plugins na cadeia (nova feature)
    - Toggle de monitor ao vivo (nova feature)
    - Toggle de auto-bounce por mudança de parâmetro (nova feature)
    - Lista de presets salvos com opção de deletar (nova feature)
    - Scan assíncrono (botão separado do síncrono)
    - Status do sounddevice além do dawdreamer
"""
from __future__ import annotations

import bpy
from bpy.types import Panel, UIList

from . import engine
from .live_monitor import _try_import_sounddevice
from .utils import get_chain
from .pressets import get_preset_manager


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
        if not engine.is_bundled():
            box = layout.box()
            box.label(text="Motor VST: dawdreamer via pip (não embutido)", icon='INFO')
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


def _draw_sounddevice_status(layout):
    """Status do sounddevice (necessário para monitor ao vivo)."""
    settings = bpy.context.scene.daw_vst
    if _try_import_sounddevice() is not None:
        return  # disponível, não precisa mostrar nada

    box = layout.box()
    box.label(text="sounddevice não instalado (monitor ao vivo)", icon='ERROR')
    if settings.is_installing_sounddevice:
        box.label(text="Instalando...", icon='SORTTIME')
    else:
        box.operator("daw.install_sounddevice", icon='IMPORT')
    if settings.sounddevice_install_log:
        col = box.column(align=True)
        for line in settings.sounddevice_install_log.splitlines()[-3:]:
            col.label(text=line)


def _draw_params_with_scroll(layout, item, is_instrument: bool):
    """
    Renderiza os parâmetros do VST com scroll e busca por nome.
    Mostra no máximo `param_display_limit` parâmetros por vez.
    """
    settings = bpy.context.scene.daw_vst
    limit = settings.param_display_limit

    if not len(item.parameters):
        return

    # Campo de busca
    row = layout.row(align=True)
    row.prop(item, "param_search", text="", icon='VIEWZOOM')

    term = item.param_search.lower().strip()
    visible_params = [
        p for p in item.parameters
        if not term or term in p.param_name.lower()
    ]

    total = len(visible_params)
    if total == 0:
        layout.label(text="Nenhum parâmetro encontrado", icon='INFO')
        return

    # Controles de scroll
    offset = max(0, min(item.param_scroll_offset, max(0, total - limit)))
    page_end = min(offset + limit, total)

    if total > limit:
        row = layout.row(align=True)
        row.label(text=f"Parâmetros {offset + 1}–{page_end} de {total}")
        up = row.operator("daw.vst_param_scroll", text="", icon='TRIA_UP')
        up.vst_id = item.vst_id
        up.direction = "UP"
        dn = row.operator("daw.vst_param_scroll", text="", icon='TRIA_DOWN')
        dn.vst_id = item.vst_id
        dn.direction = "DOWN"

    col = layout.column(align=True)
    for p in visible_params[offset:page_end]:
        row = col.row(align=True)
        row.prop(p, "param_value", text=p.param_name)
        label_text = p.param_label if p.param_label else ""
        if label_text:
            row.label(text=label_text)
        op = row.operator("daw.set_vst_parameter", text="", icon='CHECKMARK')
        op.vst_id = item.vst_id
        op.param_id = p.param_id
        op.value = p.param_value


def _draw_preset_list(layout, item):
    """
    Mostra a lista de presets salvos para este VST com botão de carregar
    e de deletar cada um.
    """
    manager = get_preset_manager()
    if not item.is_loaded:
        return

    # Precisamos do vst_name — está no item RNA
    vst_name = item.vst_name
    presets = manager.list_presets(vst_name)
    all_presets = manager.list_all_presets(vst_name)

    box = layout.box()
    box.label(text="Presets salvos", icon='FILE_TICK')

    if not presets and not all_presets:
        box.label(text="Nenhum preset salvo", icon='INFO')
    else:
        for vendor, preset_list in all_presets.items():
            col = box.column(align=True)
            col.label(text=f"[{vendor}]")
            for preset_name in preset_list:
                row = col.row(align=True)
                row.label(text=preset_name, icon='PRESET')
                op = row.operator("daw.load_vst_preset", text="", icon='LOOP_BACK')
                op.vst_id = item.vst_id
                op.preset_name = preset_name
                if vendor == "user":
                    op2 = row.operator("daw.delete_vst_preset", text="", icon='TRASH')
                    op2.vst_id = item.vst_id
                    op2.preset_name = preset_name

    row = box.row(align=True)
    op = row.operator("daw.save_vst_preset", text="Salvar Novo Preset", icon='ADD')
    op.vst_id = item.vst_id


def _draw_vst_item(layout, item, is_instrument: bool, channel_index: int, index: int, chain_len: int = 1):
    """
    Bloco de detalhe de um VST carregado: cabeçalho, parâmetros, presets.
    """
    box = layout.box()

    # ── Cabeçalho ─────────────────────────────────────────────────────
    header = box.row(align=True)
    icon_expand = 'TRIA_DOWN' if item.is_expanded else 'TRIA_RIGHT'
    header.prop(item, "is_expanded", text="", icon=icon_expand, emboss=False)

    status_icon = 'CHECKMARK' if item.is_loaded else 'ERROR'
    header.label(text=item.vst_name or "(sem nome)", icon=status_icon)

    # Bypass toggle
    bypass_icon = 'HIDE_ON' if item.bypass else 'HIDE_OFF'
    op_bypass = header.operator("daw.toggle_vst_bypass", text="", icon=bypass_icon, emboss=False)
    op_bypass.channel_index = channel_index
    op_bypass.vst_index = index
    op_bypass.is_instrument = is_instrument

    # Reorder (apenas na cadeia de efeitos, não no rack de instrumentos)
    if not is_instrument:
        if index > 0:
            op_up = header.operator("daw.move_vst_effect", text="", icon='TRIA_UP', emboss=False)
            op_up.channel_index = channel_index
            op_up.vst_index = index
            op_up.direction = "UP"
        if index < chain_len - 1:
            op_dn = header.operator("daw.move_vst_effect", text="", icon='TRIA_DOWN', emboss=False)
            op_dn.channel_index = channel_index
            op_dn.vst_index = index
            op_dn.direction = "DOWN"

    if not item.is_expanded:
        return

    # ── Corpo (expandido) ─────────────────────────────────────────────
    if item.error_message:
        box.label(text=item.error_message, icon='INFO')

    row = box.row(align=True)
    op_reload = row.operator("daw.reload_vst", text="Recarregar", icon='FILE_REFRESH')
    op_reload.channel_index = channel_index
    op_reload.vst_index = index
    op_reload.is_instrument = is_instrument

    # Parâmetros com scroll e busca
    _draw_params_with_scroll(box, item, is_instrument)

    # Presets
    _draw_preset_list(box, item)

    # Bounce (instrumento)
    if is_instrument:
        col = box.column(align=True)
        op_render = col.operator(
            "daw.render_vst_instrument_to_timeline",
            text="Bounce na Timeline", icon='RENDER_ANIMATION',
        )
        op_render.vst_id = item.vst_id

        op_rebounce = col.operator(
            "daw.auto_bounce_vst_instrument",
            text="Re-Bounce Agora", icon='FILE_REFRESH',
        )
        op_rebounce.vst_id = item.vst_id


# ---------------------------------------------------------------------- #
# Operator auxiliar: scroll de parâmetros
# ---------------------------------------------------------------------- #
class DAW_OT_VstParamScroll(bpy.types.Operator):
    bl_idname = "daw.vst_param_scroll"
    bl_label = "Scroll de Parâmetros"
    bl_description = "Navega pela lista de parâmetros do VST"
    bl_options = {'REGISTER', 'INTERNAL'}

    vst_id: bpy.props.StringProperty(default="")
    direction: bpy.props.EnumProperty(
        items=[("UP", "Para Cima", ""), ("DOWN", "Para Baixo", "")],
        default="DOWN",
    )

    def execute(self, context):
        settings = context.scene.daw_vst
        limit = settings.param_display_limit

        # Encontrar o item RNA pelo vst_id
        item = _find_rna_item(context.scene, self.vst_id)
        if item is None:
            return {'CANCELLED'}

        total = len(item.parameters)
        step = limit
        if self.direction == "UP":
            item.param_scroll_offset = max(0, item.param_scroll_offset - step)
        else:
            item.param_scroll_offset = min(max(0, total - limit), item.param_scroll_offset + step)
        return {'FINISHED'}


def _find_rna_item(scene, vst_id: str):
    """Busca o DawVstProperty RNA pelo vst_id em cadeias e rack."""
    for chain in scene.daw_vst_chains:
        for item in chain.vsts:
            if item.vst_id == vst_id:
                return item
    for item in scene.daw_vst_instruments.instruments:
        if item.vst_id == vst_id:
            return item
    return None


# ---------------------------------------------------------------------- #
# Operator: instalar sounddevice
# ---------------------------------------------------------------------- #
class DAW_OT_InstallSounddevice(bpy.types.Operator):
    bl_idname = "daw.install_sounddevice"
    bl_label = "Instalar sounddevice"
    bl_description = "Instala a biblioteca 'sounddevice' (monitor ao vivo) via pip no Python do Blender"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from .live_monitor import install_sounddevice

        settings = context.scene.daw_vst
        if _try_import_sounddevice() is not None:
            self.report({'INFO'}, "sounddevice já está instalado")
            return {'FINISHED'}

        settings.is_installing_sounddevice = True

        def _on_done(success: bool, message: str):
            def _apply():
                settings.is_installing_sounddevice = False
                settings.sounddevice_install_log = message[-400:]
                return None
            bpy.app.timers.register(_apply, first_interval=0.0)

        install_sounddevice(callback=_on_done)
        self.report({'INFO'}, "Instalando sounddevice em background...")
        return {'FINISHED'}


# ---------------------------------------------------------------------- #
# Browser de VSTs
# ---------------------------------------------------------------------- #
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

        # Dois botões de scan: síncrono (garante atualização) e assíncrono (não trava)
        scan_row = col.row(align=True)
        scan_icon = 'SORTTIME' if browser.is_scanning else 'VIEWZOOM'
        scan_row.operator("daw.scan_vst_directories_async", text="Escanear", icon=scan_icon)
        scan_row.operator("daw.scan_vst_directories", text="", icon='FILE_REFRESH')

        if browser.is_scanning:
            layout.label(text="Escaneando em background...", icon='SORTTIME')

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
        box.label(text=f"{len(visible)} plugin(s) encontrado(s)", icon='PLUGIN')
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

        settings = context.scene.daw_vst
        channel_index = _active_channel_index(context)
        # NUNCA cria a cadeia aqui dentro do draw(): o Blender proíbe
        # adicionar itens em coleções de ID durante o redraw da UI
        # ("Writing to ID classes in this context is not allowed").
        # A criação real acontece dentro de um operator (ver
        # get_or_create_chain usado pelos operators.py de VST).
        chain = get_chain(context.scene, channel_index)

        layout.label(text=f"Canal: {_active_channel_name(context)}", icon='SEQ_STRIP_DUPLICATE')

        # ── Monitor ao vivo ───────────────────────────────────────────
        monitor_box = layout.box()
        row = monitor_box.row(align=True)
        monitor_icon = 'RECORD_OFF' if settings.is_live_monitoring else 'RECORD_ON'
        monitor_label = "Parar Monitor" if settings.is_live_monitoring else "Monitor Ao Vivo"
        op_monitor = row.operator(
            "daw.toggle_vst_live_monitoring",
            text=monitor_label,
            icon=monitor_icon,
        )
        op_monitor.channel_index = channel_index

        if settings.is_live_monitoring:
            monitor_box.label(text="Processando microfone em tempo real", icon='SORTTIME')

        _draw_sounddevice_status(monitor_box)

        # ── Auto-bounce ───────────────────────────────────────────────
        layout.prop(settings, "auto_bounce_on_change", icon='FILE_REFRESH')

        if chain is None or not len(chain.vsts):
            layout.label(text="Nenhum VST de efeito neste canal.", icon='INFO')
            layout.label(text="Use o painel 'VST Browser' para adicionar um.", icon='PLUGIN')
            return

        chain_len = len(chain.vsts)
        for index, item in enumerate(chain.vsts):
            _draw_vst_item(
                layout, item,
                is_instrument=False,
                channel_index=channel_index,
                index=index,
                chain_len=chain_len,
            )
            op_rem = layout.operator("daw.remove_vst_effect", text="Remover", icon='TRASH')
            op_rem.channel_index = channel_index
            op_rem.vst_index = index

        layout.separator()
        op = layout.operator(
            "daw.apply_vst_effect_to_strip",
            text="Aplicar Cadeia a uma Strip...", icon='RENDER_ANIMATION',
        )
        op.channel_index = channel_index


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

        settings = context.scene.daw_vst
        rack = context.scene.daw_vst_instruments

        # Auto-bounce também aparece aqui (afeta instrumentos)
        layout.prop(settings, "auto_bounce_on_change", icon='FILE_REFRESH')

        if not len(rack.instruments):
            layout.label(text="Nenhum instrumento VST carregado.", icon='INFO')
            return

        for index, item in enumerate(rack.instruments):
            _draw_vst_item(
                layout, item,
                is_instrument=True,
                channel_index=-1,
                index=index,
                chain_len=len(rack.instruments),
            )
            op = layout.operator("daw.remove_vst_instrument", text="Remover", icon='TRASH')
            op.vst_index = index


classes = [
    DAW_OT_VstParamScroll,
    DAW_OT_InstallSounddevice,
    DAW_PT_VstBrowser,
    DAW_PT_VstEffects,
    DAW_PT_VstInstruments,
]
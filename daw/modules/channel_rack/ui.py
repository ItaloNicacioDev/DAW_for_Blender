# modules/channel_rack/ui.py
"""
Painéis de UI do Blender para o Channel Rack.

Segue o mesmo padrão dos outros painéis do projeto:
    - bl_space_type = 'SEQUENCE_EDITOR' (onde a DAW vive)
    - bl_category   = "Tracks" (aba própria, ver DAW_PT_ChannelRack)

Refinamento visual (pedido: aproximar da identidade visual do material
de divulgação, dentro do que os widgets nativos do Blender permitem):
    - Chips de cor sólida gerados em runtime por canal (icons.py) no
      lugar do color-picker pequeno -- mais parecido com os blocos
      coloridos cheios da imagem de referência.
    - Toolbar com botões maiores (scale_y) no topo, agrupados por
      função, em vez de uma coluna estreita ao lado da lista.
    - Seções com cabeçalho + ícone + separador, pra dar a sensação de
      "cards" distintos (mais próximo dos painéis soltos do mockup).
    - Botão "Solo" usa `alert=True` quando ativo -- o Blender pinta o
      botão num tom avermelhado nativo, igual à convenção universal de
      solo em DAWs, sem precisar de nenhuma cor customizada.
"""
from __future__ import annotations

import bpy
from bpy.types import Panel, UIList

from .icons import (
    icon_for_instrument,
    icon_for_mute,
    icon_for_solo,
    icon_for_step,
    get_color_icon_value,
    ICON_ADD,
    ICON_REMOVE,
    ICON_DUPLICATE,
    ICON_GROUP,
    ICON_LOCKED,
    ICON_UNLOCKED,
)


class DAW_UL_ChannelList(UIList):
    """Lista de canais do Channel Rack (nome, cor, mute/solo, monitor, canal VSE)."""
    bl_idname = "DAW_UL_channel_list"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        channel = item
        row = layout.row(align=True)

        # Chip de cor sólida (gerado em runtime) em vez do color-picker
        # pequeno -- funciona como identificador visual forte do track,
        # igual às barras coloridas da imagem de referência.
        row.label(text="", icon_value=get_color_icon_value(channel.color))
        row.label(text="", icon=icon_for_instrument(channel.instrument_type))

        row.prop(channel, "name", text="", emboss=False)

        row.prop(
            channel, "mute", text="",
            icon=icon_for_mute(channel.mute), emboss=False,
        )
        solo_row = row.row(align=True)
        solo_row.alert = channel.solo  # destaque nativo em vermelho quando ativo
        solo_row.prop(
            channel, "solo", text="",
            icon=icon_for_solo(channel.solo), emboss=False,
        )

        # Medidor de nível ao vivo (VU). `UILayout.progress()` só existe
        # a partir do Blender 4.0 -- guardado por segurança em versões
        # mais antigas, cai pra um label com o nível em % em vez de travar.
        meter = row.row(align=True)
        meter.scale_x = 1.6
        try:
            meter.progress(
                factor=channel.meter_level,
                type='BAR',
                text="",
            )
        except AttributeError:
            meter.label(text=f"{int(channel.meter_level * 100)}%")

        # Canal do VSE que este track controla/observa.
        row.prop(channel, "vse_channel", text="")

        row.prop(
            channel, "locked", text="",
            icon=ICON_LOCKED if channel.locked else ICON_UNLOCKED, emboss=False,
        )


class DAW_PT_ChannelRack(Panel):
    bl_label = "Channel Rack"
    bl_idname = "DAW_PT_channel_rack"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    # Aba própria ("Tracks"), separada de "DAW" onde ficam Mixer/VST
    # Browser/etc -- pedido explícito pra este painel não ficar
    # misturado com os outros. (Nota: Blender não tem um jeito de addon
    # criar uma janela/editor totalmente independente/flutuante fora do
    # sistema de abas do N-sidebar -- isso exigiria um Editor Type novo,
    # que só pode ser registrado em C dentro do próprio Blender, não via
    # addon Python. A aba dedicada é o equivalente mais próximo disso
    # que a API permite; o usuário ainda pode arrastar essa região pra
    # fora e virar uma janela separada de verdade, como qualquer região
    # do Blender.)
    bl_category = "Tracks"
    bl_order = 0

    def draw(self, context):
        layout = self.layout
        rack = context.scene.daw_channel_rack

        # --- Toolbar (maior, agrupada, no topo -- em vez de uma coluna
        # estreita espremida ao lado da lista) ---
        toolbar = layout.row(align=True)
        toolbar.scale_y = 1.4
        toolbar.operator("daw.add_channel", text="Track", icon=ICON_ADD)
        toolbar.operator("daw.duplicate_channel", text="", icon=ICON_DUPLICATE)
        toolbar.operator("daw.remove_channel", text="", icon=ICON_REMOVE)
        move = toolbar.row(align=True)
        move.operator("daw.move_channel", text="", icon='TRIA_UP').direction = "UP"
        move.operator("daw.move_channel", text="", icon='TRIA_DOWN').direction = "DOWN"

        layout.separator(factor=0.5)

        # --- Lista de canais (seleção, monitor, canal VSE, lock) ---
        layout.template_list(
            "DAW_UL_channel_list", "",
            rack, "channels",
            rack, "active_channel_index",
            rows=5,
        )

        channel = None
        if 0 <= rack.active_channel_index < len(rack.channels):
            channel = rack.channels[rack.active_channel_index]

        layout.separator(factor=1.5)

        # --- Grade com TODOS os tracks + steps visíveis ao mesmo tempo ---
        # (visual de "channel rack" clássico -- cada linha é um track
        # inteiro, com nome/mute/solo/steps visíveis simultaneamente, em
        # vez de só o canal selecionado acima. É a seção que mais se
        # aproxima do layout da imagem de referência).
        if len(rack.channels) > 0:
            box = layout.box()
            header = box.row()
            header.label(text="Tracks", icon='SEQUENCE')

            col = box.column(align=True)
            for i, ch in enumerate(rack.channels):
                row = col.row(align=True)
                row.scale_y = 1.15  # linhas mais "encorpadas", parecido com o mockup

                sel = row.operator(
                    "daw.select_channel", text="",
                    icon_value=get_color_icon_value(ch.color),
                    depress=(i == rack.active_channel_index),
                )
                sel.index = i

                name_col = row.column()
                name_col.scale_x = 1.3
                name_col.label(text=ch.name)

                row.prop(ch, "mute", text="M", toggle=True)
                solo_cell = row.row(align=True)
                solo_cell.alert = ch.solo
                solo_cell.prop(ch, "solo", text="S", toggle=True)

                grid = row.row(align=True)
                for s in range(min(rack.step_count, 16)):
                    op = grid.operator(
                        "daw.toggle_step",
                        text="",
                        icon=icon_for_step(ch.steps[s]),
                        depress=ch.steps[s],
                    )
                    op.channel_index = i
                    op.step_index = s

        layout.separator(factor=1.5)

        # --- Propriedades do canal ativo ---
        if channel is not None:
            box = layout.box()
            row = box.row()
            row.label(text="", icon_value=get_color_icon_value(channel.color))
            row.label(text=channel.name)

            box.prop(channel, "instrument_type")
            if channel.instrument_type == "SAMPLER":
                box.prop(channel, "sample_path", text="Amostra")

            row = box.row(align=True)
            row.prop(channel, "volume")
            row.prop(channel, "pan")

            row = box.row(align=True)
            row.prop(channel, "monitor_source", text="Monitor")
            row.prop(channel, "vse_channel", text="Canal VSE")

            row = box.row(align=True)
            row.operator("daw.clear_channel_steps", text="Limpar Pattern", icon='TRASH')

        # --- Steps do canal ativo (edição detalhada, todos os steps) ---
        if channel is not None:
            layout.separator(factor=1.0)
            box = layout.box()
            box.label(text=f"Pattern — {channel.name}", icon='SEQUENCE')

            grid = box.grid_flow(row_major=True, columns=8, even_columns=True, even_rows=True)
            for i in range(rack.step_count):
                op = grid.operator(
                    "daw.toggle_step",
                    text=str(i + 1),
                    icon=icon_for_step(channel.steps[i]),
                    depress=channel.steps[i],
                )
                op.channel_index = rack.active_channel_index
                op.step_index = i

        # --- Opções gerais do rack (rodapé) ---
        layout.separator(factor=1.5)
        box = layout.box()
        box.label(text="Opções do Rack", icon='SETTINGS')
        box.prop(rack, "step_count")
        box.prop(rack, "master_volume")

        row = box.row(align=True)
        row.prop(rack, "show_corner_overlay", text="Overlay no canto", icon='OVERLAY', toggle=True)
        # Botão manual pro caso do overlay ainda não ter conseguido
        # iniciar sozinho (ex.: addon foi ativado antes do workspace
        # da DAW existir) -- ensure_started() já tenta de novo
        # sozinho, mas isto dá um jeito imediato de forçar.
        reopen = row.operator("daw.channel_rack_overlay", text="", icon='FILE_REFRESH')


class DAW_PT_ChannelGroups(Panel):
    bl_label = "Grupos"
    bl_idname = "DAW_PT_channel_groups"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Tracks"
    bl_parent_id = "DAW_PT_channel_rack"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        rack = context.scene.daw_channel_rack

        row = layout.row()
        col = row.column()
        for i, group in enumerate(rack.groups):
            box = col.box()
            r = box.row(align=True)
            r.label(text="", icon_value=get_color_icon_value(group.color))
            r.prop(group, "color", text="")
            r.prop(group, "name", text="")
            r.prop(group, "muted", text="", icon=icon_for_mute(group.muted))
            op = r.operator("daw.remove_channel_group", text="", icon='X')
            op.index = i

        layout.operator("daw.add_channel_group", text="Adicionar Grupo", icon=ICON_ADD)

        channel = None
        if 0 <= rack.active_channel_index < len(rack.channels):
            channel = rack.channels[rack.active_channel_index]

        if channel is not None and len(rack.groups) > 0:
            layout.separator()
            layout.label(text=f"Grupo do canal '{channel.name}':")
            row = layout.row(align=True)
            for i, group in enumerate(rack.groups):
                op = row.operator(
                    "daw.assign_channel_to_group",
                    text=group.name,
                    depress=(channel.group_index == i),
                )
                op.channel_index = rack.active_channel_index
                op.group_index = i


classes = [
    DAW_UL_ChannelList,
    DAW_PT_ChannelRack,
    DAW_PT_ChannelGroups,
]
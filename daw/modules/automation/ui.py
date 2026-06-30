# modules/automation/ui.py
"""
Painéis de UI do Blender para o módulo de automação.

Segue o mesmo padrão dos outros painéis do projeto:
    - bl_space_type = 'SEQUENCE_EDITOR' (onde a DAW vive)
    - bl_category   = "DAW"
"""
from __future__ import annotations

import bpy


class DAW_PT_Automation(bpy.types.Panel):
    bl_label       = "Automação"
    bl_idname      = "DAW_PT_automation"
    bl_space_type  = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category    = "DAW"
    bl_order       = 5

    def draw(self, context):
        layout = self.layout
        props  = context.scene.daw_automation

        # --- Parâmetro ativo ---
        box = layout.box()
        box.label(text="Parâmetro Ativo", icon='FCURVE')
        box.prop(props, "active_param", text="")

        # --- Botões de geração rápida ---
        row = layout.row(align=True)
        op = row.operator("daw.generate_automation", text="Fade In",  icon='TRIA_UP')
        op.generator_type = "FADE_IN"
        op.target_param   = props.active_param

        op = row.operator("daw.generate_automation", text="Fade Out", icon='TRIA_DOWN')
        op.generator_type = "FADE_OUT"
        op.target_param   = props.active_param

        op = row.operator("daw.generate_automation", text="LFO", icon='SHADERFX')
        op.generator_type = "LFO"
        op.target_param   = props.active_param

        # --- Adicionar clip ---
        op = layout.operator("daw.add_automation_clip", icon='ADD')
        op.target_param = props.active_param

        # --- Configurações da curva ---
        box = layout.box()
        box.label(text="Opções", icon='SETTINGS')
        box.prop(props, "default_interpolation")
        box.prop(props, "snap_enabled")
        if props.snap_enabled:
            box.prop(props, "snap_grid")
        box.prop(props, "show_all_curves")

        # --- Limpar ---
        layout.operator("daw.clear_automation_curve", icon='TRASH')


class DAW_PT_AutomationCurveEditor(bpy.types.Panel):
    bl_label       = "Editor de Curva"
    bl_idname      = "DAW_PT_automation_curve_editor"
    bl_space_type  = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category    = "DAW"
    bl_parent_id   = "DAW_PT_automation"
    bl_options     = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        props  = context.scene.daw_automation

        row = layout.row(align=True)
        row.prop(props, "zoom_x", text="Zoom H")
        row.prop(props, "zoom_y", text="Zoom V")

        layout.separator()
        row = layout.row(align=True)
        row.operator("daw.add_automation_point",    text="+ Ponto", icon='ADD')
        row.operator("daw.remove_automation_point", text="- Ponto", icon='REMOVE')


classes = [
    DAW_PT_Automation,
    DAW_PT_AutomationCurveEditor,
]
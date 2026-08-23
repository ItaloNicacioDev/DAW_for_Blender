# modules/automation/operators.py
"""
Operadores do módulo de automação: novo clip, gerar curva pronta
(fade in/out, LFO), adicionar/remover ponto de controle, limpar curva.

CORREÇÃO: este arquivo continha, por engano, uma cópia do conteúdo de
`properties.py` (mesmas classes PropertyGroup, cabeçalho dizendo
"# modules/automation/properties.py") -- não tinha nenhum
`bpy.types.Operator` nem a lista `classes` que `register.py` importa
(`from .operators import classes as operator_classes`), por isso o
módulo inteiro falhava com
`ImportError: cannot import name 'classes' from 'daw.modules.automation.operators'`
e derrubava a automação inteira. Os operadores abaixo implementam o
que `ui.py` já esperava (os `bl_idname` usados lá: daw.add_automation_clip,
daw.generate_automation, daw.clear_automation_curve,
daw.add_automation_point, daw.remove_automation_point).

Armazenamento: os `AutomationClip` ficam num registro em memória por
cena (`_clips_by_scene`) -- ainda não existe uma ponte com
`daw_engine/core/timeline.py` real (o Scheduler ainda não lê esses
clips durante a reprodução, igual ao Channel Rack). Isso é suficiente
pra UI funcionar de ponta a ponta (criar clip, gerar/editar curva)
enquanto essa ponte não é construída à parte.
"""
from __future__ import annotations

import bpy
from bpy.props import EnumProperty, FloatProperty, StringProperty
from bpy.types import Operator

from . import generators
from .clips import AutomationClip
from .interpolation import InterpolationMode


# ------------------------------------------------------------------
# Armazenamento em memória (por cena) dos clips de automação
# ------------------------------------------------------------------
_clips_by_scene: dict = {}   # {scene.name: [AutomationClip, ...]}


def get_clips(scene) -> list:
    return _clips_by_scene.setdefault(scene.name, [])


def get_active_clip(scene, props):
    clips = get_clips(scene)
    idx = props.selected_clip_index
    if 0 <= idx < len(clips):
        return clips[idx]
    return None


def _playhead_seconds(scene) -> float:
    fps = scene.render.fps / max(scene.render.fps_base, 0.0001)
    return scene.frame_current / fps if fps else 0.0


def _tag_redraw(context):
    try:
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'SEQUENCE_EDITOR':
                    area.tag_redraw()
    except Exception:
        pass


# ------------------------------------------------------------------
# Operadores
# ------------------------------------------------------------------

class DAW_OT_AddAutomationClip(Operator):
    """Cria um novo clip de automação na posição atual do playhead"""
    bl_idname = "daw.add_automation_clip"
    bl_label = "Novo Clip de Automação"
    bl_options = {'REGISTER', 'UNDO'}

    target_param: StringProperty(name="Parâmetro", default="volume")
    duration: FloatProperty(name="Duração (s)", default=4.0, min=0.1, soft_max=60.0)

    def execute(self, context):
        scene = context.scene
        props = scene.daw_automation
        start = _playhead_seconds(scene)

        clip = AutomationClip(name=self.target_param, start=start, duration=self.duration)
        clip.add_curve(self.target_param, 0.0, 1.0, 0.5)

        clips = get_clips(scene)
        clips.append(clip)
        props.selected_clip_index = len(clips) - 1
        props.active_param = self.target_param

        self.report({'INFO'}, f"Clip de automação '{self.target_param}' criado em {start:.2f}s")
        _tag_redraw(context)
        return {'FINISHED'}


class DAW_OT_GenerateAutomation(Operator):
    """Gera uma curva pronta (fade in/out ou LFO) pro parâmetro ativo,
    substituindo os pontos existentes no clip selecionado. Se nenhum
    clip estiver selecionado, cria um automaticamente no playhead."""
    bl_idname = "daw.generate_automation"
    bl_label = "Gerar Automação"
    bl_options = {'REGISTER', 'UNDO'}

    generator_type: EnumProperty(
        name="Tipo",
        items=(
            ('FADE_IN', "Fade In", "Sobe de 0 até o máximo"),
            ('FADE_OUT', "Fade Out", "Desce do máximo até 0"),
            ('LFO', "LFO", "Oscilação periódica (vibrato/tremolo)"),
        ),
        default='FADE_IN',
    )
    target_param: StringProperty(name="Parâmetro", default="volume")

    def execute(self, context):
        scene = context.scene
        props = scene.daw_automation

        clip = get_active_clip(scene, props)
        if clip is None:
            start = _playhead_seconds(scene)
            clip = AutomationClip(name=self.target_param, start=start, duration=4.0)
            clips = get_clips(scene)
            clips.append(clip)
            props.selected_clip_index = len(clips) - 1

        curve = clip.get_curve(self.target_param) or clip.add_curve(self.target_param, 0.0, 1.0, 0.5)
        curve.clear()

        duration = clip.duration
        if self.generator_type == 'FADE_IN':
            generated = generators.generate_fade_in(self.target_param, duration, curve.min_val, curve.max_val)
        elif self.generator_type == 'FADE_OUT':
            generated = generators.generate_fade_out(self.target_param, duration, curve.min_val, curve.max_val)
        else:
            generated = generators.generate_lfo(
                self.target_param, rate_hz=1.0, depth=1.0, center=0.5,
                duration=duration, min_val=curve.min_val, max_val=curve.max_val,
            )

        for pt in generated.points:
            curve.add_point(pt.time, pt.value, pt.mode)

        props.active_param = self.target_param
        self.report({'INFO'}, f"{self.generator_type} gerado para '{self.target_param}'")
        _tag_redraw(context)
        return {'FINISHED'}


class DAW_OT_ClearAutomationCurve(Operator):
    """Remove todos os pontos da curva do parâmetro ativo, no clip selecionado"""
    bl_idname = "daw.clear_automation_curve"
    bl_label = "Limpar Curva"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return hasattr(scene, "daw_automation") and get_active_clip(scene, scene.daw_automation) is not None

    def execute(self, context):
        scene = context.scene
        props = scene.daw_automation
        clip = get_active_clip(scene, props)
        curve = clip.get_curve(props.active_param) if clip else None
        if curve is None:
            self.report({'WARNING'}, f"Sem curva para '{props.active_param}' neste clip")
            return {'CANCELLED'}

        curve.clear()
        _tag_redraw(context)
        return {'FINISHED'}


class DAW_OT_AddAutomationPoint(Operator):
    """Adiciona um ponto de controle na posição atual do playhead"""
    bl_idname = "daw.add_automation_point"
    bl_label = "Adicionar Ponto"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return hasattr(scene, "daw_automation") and get_active_clip(scene, scene.daw_automation) is not None

    def execute(self, context):
        scene = context.scene
        props = scene.daw_automation
        clip = get_active_clip(scene, props)
        if clip is None:
            self.report({'WARNING'}, "Nenhum clip de automação selecionado")
            return {'CANCELLED'}

        curve = clip.get_curve(props.active_param) or clip.add_curve(props.active_param, 0.0, 1.0, 0.5)

        time = _playhead_seconds(scene) - clip.start
        value = curve.evaluate(time) if len(curve) else curve.default_val
        mode = InterpolationMode(props.default_interpolation)
        curve.add_point(time, value, mode)

        _tag_redraw(context)
        return {'FINISHED'}


class DAW_OT_RemoveAutomationPoint(Operator):
    """Remove o ponto de controle mais próximo do playhead"""
    bl_idname = "daw.remove_automation_point"
    bl_label = "Remover Ponto"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return hasattr(scene, "daw_automation") and get_active_clip(scene, scene.daw_automation) is not None

    def execute(self, context):
        scene = context.scene
        props = scene.daw_automation
        clip = get_active_clip(scene, props)
        curve = clip.get_curve(props.active_param) if clip else None
        if not curve or len(curve) == 0:
            self.report({'WARNING'}, "Nenhum ponto pra remover")
            return {'CANCELLED'}

        time = _playhead_seconds(scene) - clip.start
        nearest_idx = min(range(len(curve.points)), key=lambda i: abs(curve.points[i].time - time))
        curve.remove_point(nearest_idx)

        _tag_redraw(context)
        return {'FINISHED'}


classes = [
    DAW_OT_AddAutomationClip,
    DAW_OT_GenerateAutomation,
    DAW_OT_ClearAutomationCurve,
    DAW_OT_AddAutomationPoint,
    DAW_OT_RemoveAutomationPoint,
]
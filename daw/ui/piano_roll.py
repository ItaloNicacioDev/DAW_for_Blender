"""
ui/piano_roll.py

Piano Roll completo para o Blender DAW.
Desenhado com o módulo gpu do Blender (OpenGL/shaders).

Funcionalidades:
  - Desenhar/apagar notas com mouse
  - Zoom horizontal e vertical (scroll do mouse)
  - Scroll com botão do meio
  - Snap ao grid (quantização: 1/4, 1/8, 1/16)
  - Playhead sincronizado com o engine
  - Teclas de piano clicáveis na lateral
  - 128 notas MIDI (C-1 a G9)
  - Strips MIDI no Sequencer
"""

import bpy
import gpu
import blf
from gpu_extras.batch import batch_for_shader
from bpy.props import (FloatProperty, IntProperty, BoolProperty,
                       EnumProperty, CollectionProperty, StringProperty)
import math
from typing import List, Tuple


# ═══════════════════════════════════════════════════════════════
#  CONSTANTES DE LAYOUT
# ═══════════════════════════════════════════════════════════════

PIANO_WIDTH      = 64
HEADER_HEIGHT    = 24
NOTE_HEIGHT_BASE = 12
BEAT_WIDTH_BASE  = 80
TOTAL_NOTES      = 128
SCROLLBAR_SIZE   = 12

COL_BG           = (0.12, 0.12, 0.14, 1.0)
COL_BG_DARK      = (0.08, 0.08, 0.10, 1.0)
COL_BLACK_KEY    = (0.10, 0.10, 0.12, 1.0)
COL_WHITE_KEY    = (0.22, 0.22, 0.25, 1.0)
COL_KEY_HOVER    = (0.30, 0.30, 0.35, 1.0)
COL_GRID_LINE    = (0.20, 0.20, 0.23, 1.0)
COL_GRID_BEAT    = (0.25, 0.25, 0.28, 1.0)
COL_GRID_BAR     = (0.35, 0.35, 0.40, 1.0)
COL_NOTE         = (0.20, 0.65, 0.95, 1.0)
COL_NOTE_SEL     = (0.30, 0.85, 1.00, 1.0)
COL_NOTE_DARK    = (0.12, 0.45, 0.72, 1.0)
COL_PLAYHEAD     = (1.00, 0.35, 0.35, 1.0)
COL_HEADER       = (0.10, 0.10, 0.13, 1.0)
COL_HEADER_TEXT  = (0.70, 0.70, 0.75, 1.0)
COL_OCTAVE_LINE  = (0.40, 0.40, 0.50, 0.4)

BLACK_NOTES = {1, 3, 6, 8, 10}
NOTE_NAMES  = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']


# ═══════════════════════════════════════════════════════════════
#  ESTRUTURAS DE DADOS
# ═══════════════════════════════════════════════════════════════

class MidiNote(bpy.types.PropertyGroup):
    pitch:    IntProperty(min=0, max=127)
    start:    FloatProperty()
    length:   FloatProperty()
    velocity: IntProperty(min=1, max=127, default=100)
    selected: BoolProperty(default=False)


# [NOVO] Container de notas por strip
class MidiStripData(bpy.types.PropertyGroup):
    strip_name: StringProperty()
    notes:      CollectionProperty(type=MidiNote)


class PianoRollState(bpy.types.PropertyGroup):
    notes: CollectionProperty(type=MidiNote)  # fallback global

    zoom_x:   FloatProperty(default=1.0, min=0.1, max=8.0)
    zoom_y:   FloatProperty(default=1.0, min=0.3, max=4.0)
    scroll_x: FloatProperty(default=0.0, min=0.0)
    scroll_y: FloatProperty(default=48.0, min=0.0, max=127.0)

    snap_mode: EnumProperty(
        items=[
            ('1',      '1/1',  'Compasso inteiro'),
            ('0.5',    '1/2',  'Meia nota'),
            ('0.25',   '1/4',  'Quarta nota'),
            ('0.125',  '1/8',  'Oitava nota'),
            ('0.0625', '1/16', 'Décima sexta nota'),
        ],
        default='0.25',
        name="Snap"
    )

    active_track: IntProperty(default=0)
    total_beats:  FloatProperty(default=32.0)

    # [NOVO] strip ativo e lista de strips
    active_strip: StringProperty(default="")
    midi_strips:  CollectionProperty(type=MidiStripData)


# [NOVO] Helper: retorna notas do strip ativo ou fallback global
def _get_active_notes(state):
    if state.active_strip:
        for ms in state.midi_strips:
            if ms.strip_name == state.active_strip:
                return ms.notes
    return state.notes


# ═══════════════════════════════════════════════════════════════
#  HELPERS DE DESENHO  (inalterados)
# ═══════════════════════════════════════════════════════════════

_shader = None

def _get_shader():
    global _shader
    if _shader is None:
        _shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    return _shader


def _draw_rect(x, y, w, h, color):
    if w <= 0 or h <= 0:
        return
    shader = _get_shader()
    batch = batch_for_shader(shader, 'TRIS', {"pos": [
        (x, y), (x+w, y), (x+w, y+h),
        (x, y), (x+w, y+h), (x, y+h),
    ]})
    shader.uniform_float("color", color)
    batch.draw(shader)


def _draw_line(x1, y1, x2, y2, color):
    shader = _get_shader()
    batch = batch_for_shader(shader, 'LINES', {"pos": [(x1, y1), (x2, y2)]})
    shader.uniform_float("color", color)
    batch.draw(shader)


def _draw_text(text, x, y, size, color):
    blf.size(0, size)
    blf.color(0, *color)
    blf.position(0, x, y, 0)
    blf.draw(0, text)


def _note_name(midi):
    return f"{NOTE_NAMES[midi % 12]}{(midi // 12) - 1}"

def _is_black(midi):
    return (midi % 12) in BLACK_NOTES


# ═══════════════════════════════════════════════════════════════
#  PIANO ROLL — DRAW HANDLER
# ═══════════════════════════════════════════════════════════════

def _draw_piano_roll(context):
    state = context.scene.piano_roll
    region = context.region
    W, H = region.width, region.height

    grid_x = PIANO_WIDTH
    grid_y = HEADER_HEIGHT
    grid_w = W - PIANO_WIDTH - SCROLLBAR_SIZE
    grid_h = H - HEADER_HEIGHT - SCROLLBAR_SIZE

    note_h  = NOTE_HEIGHT_BASE * state.zoom_y
    beat_w  = BEAT_WIDTH_BASE  * state.zoom_x

    visible_notes = int(grid_h / note_h) + 2
    visible_beats = grid_w / beat_w

    top_note = min(int(state.scroll_y + visible_notes / 2), 127)
    snap = float(state.snap_mode)

    gpu.state.blend_set('ALPHA')

    _draw_rect(0, 0, W, H, COL_BG_DARK)

    # ── Grid de notas ────────────────────────────────────────
    for i in range(visible_notes + 1):
        note = top_note - i
        if note < 0 or note > 127:
            continue
        ny = grid_y + grid_h - (i + 1) * note_h + (state.scroll_y % 1) * note_h
        col = COL_BLACK_KEY if _is_black(note) else COL_BG
        _draw_rect(grid_x, ny, grid_w, note_h - 0.5, col)
        if note % 12 == 0:
            _draw_line(grid_x, ny + note_h, grid_x + grid_w, ny + note_h, COL_OCTAVE_LINE)

    # ── Grid vertical ────────────────────────────────────────
    start_beat  = state.scroll_x
    beat_offset = (start_beat % 1) * beat_w
    b = 0
    while True:
        bx = grid_x + b * beat_w * snap / snap - beat_offset
        if bx > grid_x + grid_w:
            break
        beat_abs = start_beat + b * snap
        is_bar   = abs(beat_abs % 4) < 0.001
        if bx >= grid_x:
            col = COL_GRID_BAR if is_bar else (
                  COL_GRID_BEAT if abs(beat_abs % 1) < 0.001 else COL_GRID_LINE)
            _draw_line(bx, grid_y, bx, grid_y + grid_h, col)
            if is_bar:
                bar_num = int(beat_abs / 4) + 1
                _draw_text(str(bar_num), bx + 3, grid_y + grid_h - 16, 11, COL_HEADER_TEXT)
        b += 1
        if b > 2000:
            break

    # ── Notas MIDI — usa strip ativo ─────────────────────────
    for note in _get_active_notes(state):
        pitch  = note.pitch
        start  = note.start
        length = note.length

        note_idx = top_note - pitch
        ny = grid_y + grid_h - (note_idx + 1) * note_h + (state.scroll_y % 1) * note_h

        if ny + note_h < grid_y or ny > grid_y + grid_h:
            continue

        nx = grid_x + (start - state.scroll_x) * beat_w
        nw = max(length * beat_w - 1, 4)

        if nx + nw < grid_x or nx > grid_x + grid_w:
            continue

        nx_clip = max(nx, grid_x)
        nw_clip = nw - (nx_clip - nx)

        col_body = COL_NOTE_SEL if note.selected else COL_NOTE
        _draw_rect(nx_clip, ny + 1, nw_clip, note_h - 2, col_body)
        _draw_rect(nx_clip, ny + note_h - 3, nw_clip, 2, COL_NOTE_DARK)

        if nw_clip > 20 and note_h > 8:
            _draw_text(_note_name(pitch), nx_clip + 3, ny + 3, 9, (0.05, 0.05, 0.08, 1.0))

    # ── Playhead — corrigido import relativo ─────────────────
    try:
        from .register import get_engine
        engine = get_engine()
        if engine and engine.running:
            s = engine.get_state()
            if s:
                ph_x = grid_x + (s.position_beats - state.scroll_x) * beat_w
                if grid_x <= ph_x <= grid_x + grid_w:
                    _draw_rect(ph_x - 1, grid_y, 2, grid_h, COL_PLAYHEAD)
                    shader = _get_shader()
                    batch = batch_for_shader(shader, 'TRIS', {"pos": [
                        (ph_x - 6, grid_y + grid_h),
                        (ph_x + 6, grid_y + grid_h),
                        (ph_x,     grid_y + grid_h - 10),
                    ]})
                    shader.uniform_float("color", COL_PLAYHEAD)
                    batch.draw(shader)
    except Exception:
        pass

    # ── Teclado lateral ──────────────────────────────────────
    _draw_rect(0, grid_y, PIANO_WIDTH, grid_h, COL_BG_DARK)
    for i in range(visible_notes + 1):
        note = top_note - i
        if note < 0 or note > 127:
            continue
        ny = grid_y + grid_h - (i + 1) * note_h + (state.scroll_y % 1) * note_h
        is_black = _is_black(note)
        col = COL_BLACK_KEY if is_black else COL_WHITE_KEY
        pw  = PIANO_WIDTH - 4 if is_black else PIANO_WIDTH - 1
        _draw_rect(1, ny + 0.5, pw, note_h - 1, col)
        if note % 12 == 0 and note_h > 8:
            _draw_text(_note_name(note), pw - 28, ny + 2, 9, (0.6, 0.6, 0.7, 1.0))
    _draw_line(PIANO_WIDTH, grid_y, PIANO_WIDTH, grid_y + grid_h, (0.30, 0.30, 0.35, 1.0))

    # ── Header ───────────────────────────────────────────────
    _draw_rect(0, grid_y + grid_h, W, HEADER_HEIGHT, COL_HEADER)
    _draw_rect(grid_x, grid_y + grid_h, grid_w, HEADER_HEIGHT, COL_HEADER)
    b = 0
    while True:
        bx = grid_x + b * beat_w - (state.scroll_x % 1) * beat_w
        if bx > grid_x + grid_w:
            break
        beat_abs = state.scroll_x + b
        if bx >= grid_x and abs(beat_abs % 4) < 0.001:
            bar_num = int(beat_abs / 4) + 1
            _draw_text(str(bar_num), bx + 3, grid_y + grid_h + 6, 11, COL_HEADER_TEXT)
            _draw_line(bx, grid_y + grid_h, bx, grid_y + grid_h + HEADER_HEIGHT, COL_GRID_BAR)
        elif bx >= grid_x and abs(beat_abs % 1) < 0.001:
            _draw_line(bx, grid_y + grid_h, bx, grid_y + grid_h + HEADER_HEIGHT // 2, COL_GRID_LINE)
        b += 1
        if b > 2000:
            break

    snap_labels = {'1':'1/1','0.5':'1/2','0.25':'1/4','0.125':'1/8','0.0625':'1/16'}
    strip_label = f"  |  Strip: {state.active_strip}" if state.active_strip else ""
    _draw_text(f"Snap: {snap_labels.get(state.snap_mode,'?')}{strip_label}",
               4, grid_y + grid_h + 7, 10, COL_HEADER_TEXT)

    # ── Scrollbars ───────────────────────────────────────────
    sb_w = grid_w
    _draw_rect(grid_x, 0, sb_w, SCROLLBAR_SIZE - 2, (0.15, 0.15, 0.18, 1.0))
    total_w = state.total_beats * beat_w
    thumb_w = max(sb_w * (sb_w / max(total_w, sb_w + 1)), 20)
    thumb_x = grid_x + (state.scroll_x / max(state.total_beats, 1)) * (sb_w - thumb_w)
    _draw_rect(thumb_x, 1, thumb_w, SCROLLBAR_SIZE - 4, (0.35, 0.35, 0.42, 1.0))

    sv_x = W - SCROLLBAR_SIZE
    _draw_rect(sv_x, grid_y, SCROLLBAR_SIZE - 2, grid_h, (0.15, 0.15, 0.18, 1.0))
    thumb_h = max(grid_h * (visible_notes / TOTAL_NOTES), 20)
    thumb_y = grid_y + grid_h - (state.scroll_y / 127.0) * (grid_h - thumb_h) - thumb_h
    _draw_rect(sv_x + 1, thumb_y, SCROLLBAR_SIZE - 4, thumb_h, (0.35, 0.35, 0.42, 1.0))

    gpu.state.blend_set('NONE')


# ═══════════════════════════════════════════════════════════════
#  OPERADOR MODAL  (inalterado, só troca state.notes por _get_active_notes)
# ═══════════════════════════════════════════════════════════════

class DAW_OT_PianoRollModal(bpy.types.Operator):
    bl_idname  = "daw.piano_roll_modal"
    bl_label   = "Piano Roll"
    bl_options = {'REGISTER'}

    _handle          = None
    _dragging        = False
    _drag_mode       = None
    _last_x          = 0
    _last_y          = 0
    _active_note_idx = -1

    def _px_to_beat(self, x, state, region):
        return state.scroll_x + (x - PIANO_WIDTH) / (BEAT_WIDTH_BASE * state.zoom_x)

    def _px_to_note(self, y, state, region):
        grid_h   = region.height - HEADER_HEIGHT - SCROLLBAR_SIZE
        note_h   = NOTE_HEIGHT_BASE * state.zoom_y
        top_note = int(state.scroll_y + (grid_h / note_h) / 2)
        return top_note - int((HEADER_HEIGHT + grid_h - y) / note_h)

    def _snap(self, beat, state):
        s = float(state.snap_mode)
        return round(beat / s) * s

    def _find_note_at(self, beat, pitch, state):
        for i, n in enumerate(_get_active_notes(state)):
            if n.pitch == pitch and n.start <= beat < n.start + n.length:
                return i
        return -1

    def _add_note(self, beat, pitch, state):
        snapped = self._snap(beat, state)
        if self._find_note_at(snapped, pitch, state) >= 0:
            return -1
        notes = _get_active_notes(state)
        note = notes.add()
        note.pitch    = max(0, min(127, pitch))
        note.start    = max(0, snapped)
        note.length   = float(state.snap_mode)
        note.velocity = 100
        return len(notes) - 1

    def _remove_note(self, beat, pitch, state):
        idx = self._find_note_at(beat, pitch, state)
        if idx >= 0:
            _get_active_notes(state).remove(idx)

    def invoke(self, context, event):
        if context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, "Abra em uma área VIEW_3D")
            return {'CANCELLED'}
        self._handle = bpy.types.SpaceView3D.draw_handler_add(
            _draw_piano_roll, (context,), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        context.area.tag_redraw()
        state  = context.scene.piano_roll
        region = context.region
        mx, my = event.mouse_region_x, event.mouse_region_y

        grid_h = region.height - HEADER_HEIGHT - SCROLLBAR_SIZE
        beat_w = BEAT_WIDTH_BASE * state.zoom_x
        note_h = NOTE_HEIGHT_BASE * state.zoom_y

        in_grid = (PIANO_WIDTH <= mx <= region.width - SCROLLBAR_SIZE and
                   HEADER_HEIGHT <= my <= HEADER_HEIGHT + grid_h)

        if event.type == 'ESC':
            self._cleanup(context)
            return {'FINISHED'}

        if event.type == 'WHEELUPMOUSE':
            if event.ctrl:   state.zoom_x = min(state.zoom_x * 1.15, 8.0)
            elif event.shift: state.zoom_y = min(state.zoom_y * 1.15, 4.0)
            else:             state.scroll_y = min(state.scroll_y + 1, 127.0)
            return {'RUNNING_MODAL'}

        if event.type == 'WHEELDOWNMOUSE':
            if event.ctrl:   state.zoom_x = max(state.zoom_x / 1.15, 0.1)
            elif event.shift: state.zoom_y = max(state.zoom_y / 1.15, 0.3)
            else:             state.scroll_y = max(state.scroll_y - 1, 0.0)
            return {'RUNNING_MODAL'}

        if event.type == 'ONE'   and event.value == 'PRESS': state.snap_mode = '1'
        if event.type == 'TWO'   and event.value == 'PRESS': state.snap_mode = '0.5'
        if event.type == 'THREE' and event.value == 'PRESS': state.snap_mode = '0.25'
        if event.type == 'FOUR'  and event.value == 'PRESS': state.snap_mode = '0.125'
        if event.type == 'FIVE'  and event.value == 'PRESS': state.snap_mode = '0.0625'

        if event.type == 'MIDDLEMOUSE':
            if event.value == 'PRESS':
                self._dragging = True; self._drag_mode = 'SCROLL'
                self._last_x, self._last_y = mx, my
            else:
                self._dragging = False; self._drag_mode = None
            return {'RUNNING_MODAL'}

        if self._dragging and self._drag_mode == 'SCROLL' and event.type == 'MOUSEMOVE':
            state.scroll_x = max(0, state.scroll_x - (mx - self._last_x) / beat_w)
            state.scroll_y = max(0, min(127, state.scroll_y + (my - self._last_y) / note_h))
            self._last_x, self._last_y = mx, my
            return {'RUNNING_MODAL'}

        if event.type == 'LEFTMOUSE' and in_grid:
            beat  = self._px_to_beat(mx, state, region)
            pitch = self._px_to_note(my, state, region)
            if event.value == 'PRESS':
                if event.ctrl:
                    self._drag_mode = 'NOTE_ERASE'
                    self._remove_note(beat, pitch, state)
                else:
                    self._drag_mode = 'NOTE_DRAW'
                    self._active_note_idx = self._add_note(beat, pitch, state)
                self._dragging = True
                self._last_x, self._last_y = mx, my
            elif event.value == 'RELEASE':
                self._dragging = False; self._drag_mode = None; self._active_note_idx = -1
            return {'RUNNING_MODAL'}

        if event.type == 'MOUSEMOVE' and self._dragging:
            beat  = self._px_to_beat(mx, state, region)
            pitch = self._px_to_note(my, state, region)
            if self._drag_mode == 'NOTE_DRAW':
                notes = _get_active_notes(state)
                if 0 <= self._active_note_idx < len(notes):
                    note = notes[self._active_note_idx]
                    snap = float(state.snap_mode)
                    note.length = max(snap, self._snap(beat - note.start + snap, state))
            elif self._drag_mode == 'NOTE_ERASE':
                self._remove_note(beat, pitch, state)
            return {'RUNNING_MODAL'}

        if event.type == 'RIGHTMOUSE' and event.value == 'PRESS' and in_grid:
            beat  = self._px_to_beat(mx, state, region)
            pitch = self._px_to_note(my, state, region)
            self._remove_note(beat, pitch, state)
            return {'RUNNING_MODAL'}

        return {'PASS_THROUGH'}

    def _cleanup(self, context):
        if self._handle:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            self._handle = None
        context.area.tag_redraw()


# ═══════════════════════════════════════════════════════════════
#  OPERADOR — Abre Piano Roll numa área VIEW_3D  (inalterado)
# ═══════════════════════════════════════════════════════════════

class DAW_OT_OpenPianoRoll(bpy.types.Operator):
    bl_idname = "daw.open_piano_roll"
    bl_label  = "Abrir Piano Roll"

    def execute(self, context):
        context.area.type = 'VIEW_3D'
        context.space_data.overlay.show_overlays = False
        context.space_data.show_gizmo = False
        context.space_data.shading.type = 'SOLID'
        bpy.ops.daw.piano_roll_modal('INVOKE_DEFAULT')
        return {'FINISHED'}


# ═══════════════════════════════════════════════════════════════
#  [NOVO] STRIP MIDI — cria strip no Sequencer vinculado ao Piano Roll
# ═══════════════════════════════════════════════════════════════

class DAW_OT_NewMidiStrip(bpy.types.Operator):
    bl_idname   = "daw.new_midi_strip"
    bl_label    = "Nova Track MIDI"
    bl_description = "Cria strip MIDI no Sequencer e abre o Piano Roll"

    def execute(self, context):
        scene = context.scene
        state = scene.piano_roll
        seq   = scene.sequence_editor_create()

        # Canal livre
        used = {s.channel for s in seq.sequences_all}
        ch = 1
        while ch in used:
            ch += 1

        # Nome único
        idx  = len(state.midi_strips) + 1
        name = f"MIDI {idx:02d}"

        # Strip de cor verde como placeholder visual
        fps   = scene.render.fps
        start = scene.frame_current
        end   = start + fps * 4
        strip = seq.sequences.new_effect(
            name=name, type='COLOR',
            channel=ch, frame_start=start, frame_end=end)
        strip.color = (0.10, 0.48, 0.32)

        # Registra dados MIDI para este strip
        ms = state.midi_strips.add()
        ms.strip_name = name

        # Ativa este strip e abre o piano roll
        state.active_strip = name
        bpy.ops.daw.open_piano_roll('INVOKE_DEFAULT')
        self.report({'INFO'}, f"Track '{name}' criada")
        return {'FINISHED'}


class DAW_OT_SelectMidiStrip(bpy.types.Operator):
    bl_idname  = "daw.select_midi_strip"
    bl_label   = "Editar Strip"
    strip_name: StringProperty()

    def execute(self, context):
        context.scene.piano_roll.active_strip = self.strip_name
        bpy.ops.daw.open_piano_roll('INVOKE_DEFAULT')
        return {'FINISHED'}


# ═══════════════════════════════════════════════════════════════
#  [NOVO] TIMER — redraw automático para playhead
# ═══════════════════════════════════════════════════════════════

def _sync_playhead():
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    except Exception:
        pass
    return 1 / 30


# ═══════════════════════════════════════════════════════════════
#  PANEL
# ═══════════════════════════════════════════════════════════════

class DAW_PT_PianoRoll(bpy.types.Panel):
    bl_label      = "Piano Roll"
    bl_idname     = "DAW_PT_piano_roll"
    bl_space_type = 'SEQUENCE_EDITOR'
    bl_region_type= 'UI'
    bl_category   = "DAW"
    bl_order      = 1

    def draw(self, context):
        layout = self.layout
        state  = context.scene.piano_roll

        # [NOVO] Botão de nova track MIDI
        layout.operator("daw.new_midi_strip", icon='ADD', text="Nova Track MIDI")
        layout.separator()

        # [NOVO] Lista de strips existentes
        if len(state.midi_strips) > 0:
            box = layout.box()
            box.label(text="Tracks MIDI:", icon='SEQUENCE')
            for ms in state.midi_strips:
                row = box.row(align=True)
                is_active = ms.strip_name == state.active_strip
                op = row.operator("daw.select_midi_strip",
                                  text=ms.strip_name,
                                  icon='PLAY' if is_active else 'DOT')
                op.strip_name = ms.strip_name
                row.label(text=f"{len(ms.notes)} notas")
            layout.separator()

        # Botão abrir piano roll (fallback sem strip)
        layout.operator("daw.open_piano_roll", icon='PIANO', text="Abrir Piano Roll")
        layout.separator()

        box2 = layout.box()
        box2.label(text="Visualização", icon='VIEW_ZOOM')
        row = box2.row(align=True)
        row.label(text="Zoom X:")
        row.prop(state, "zoom_x", text="")
        row = box2.row(align=True)
        row.label(text="Zoom Y:")
        row.prop(state, "zoom_y", text="")

        box3 = layout.box()
        box3.label(text="Quantização (Snap)", icon='SNAP_INCREMENT')
        box3.prop(state, "snap_mode", text="")
        box3.label(text="Atalhos: 1=1/1  2=1/2  3=1/4  4=1/8  5=1/16", icon='INFO')

        notes = _get_active_notes(state)
        box4 = layout.box()
        box4.label(text=f"Notas: {len(notes)}", icon='MODIFIER')
        if len(notes) > 0:
            box4.operator("daw.clear_notes", icon='TRASH', text="Limpar todas")

        box5 = layout.box()
        box5.label(text="Controles:", icon='MOUSE_LMB')
        col = box5.column(align=True)
        col.scale_y = 0.8
        col.label(text="LMB: Desenhar nota")
        col.label(text="RMB / Ctrl+LMB: Apagar")
        col.label(text="Scroll: Mover vertical")
        col.label(text="Ctrl+Scroll: Zoom X")
        col.label(text="Shift+Scroll: Zoom Y")
        col.label(text="MMB+Drag: Scroll livre")
        col.label(text="ESC: Fechar Piano Roll")


class DAW_OT_ClearNotes(bpy.types.Operator):
    bl_idname = "daw.clear_notes"
    bl_label  = "Limpar Notas"

    def execute(self, context):
        _get_active_notes(context.scene.piano_roll).clear()
        return {'FINISHED'}


# ═══════════════════════════════════════════════════════════════
#  REGISTRO
# ═══════════════════════════════════════════════════════════════

classes = [
    MidiNote,
    MidiStripData,        # [NOVO]
    PianoRollState,
    DAW_OT_PianoRollModal,
    DAW_OT_OpenPianoRoll,
    DAW_OT_ClearNotes,
    DAW_OT_NewMidiStrip,      # [NOVO]
    DAW_OT_SelectMidiStrip,   # [NOVO]
    DAW_PT_PianoRoll,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.piano_roll = bpy.props.PointerProperty(type=PianoRollState)
    # [NOVO] Timer para redraw do playhead
    if not bpy.app.timers.is_registered(_sync_playhead):
        bpy.app.timers.register(_sync_playhead, persistent=True)


def unregister():
    if bpy.app.timers.is_registered(_sync_playhead):
        bpy.app.timers.unregister(_sync_playhead)
    del bpy.types.Scene.piano_roll
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


"""
ui/piano_roll.py — v4 (FL Studio Style)

Piano Roll visual inspirado no FL Studio:
- Paleta dark green (fundo escuro, notas verdes)
- Toolbar com modos: Desenhar / Selecionar / Apagar / Pan
- Velocity lane na parte inferior (como FL Studio)
- Abre como janela flutuante independente
- Strips MIDI vinculados ao Sequence Editor
- Playhead amarelo sincronizado com motor de áudio
- Timer de redraw a 30fps
"""

import bpy
import gpu
import blf
from gpu_extras.batch import batch_for_shader
from bpy.props import (FloatProperty, IntProperty, BoolProperty,
                       EnumProperty, CollectionProperty, StringProperty)

# ═══════════════════════════════════════════════════════════════
#  CONSTANTES DE LAYOUT
# ═══════════════════════════════════════════════════════════════

PIANO_W     = 56
TOOLBAR_H   = 34
HEADER_H    = 22
VELOCITY_H  = 72
SCROLLBAR   = 11
NOTE_H_BASE = 14
BEAT_W_BASE = 80
TOTAL_NOTES = 128

# Paleta FL Studio dark
C = {
    # Interface
    'toolbar':      (0.085, 0.090, 0.130, 1.0),
    'btn':          (0.160, 0.170, 0.230, 1.0),
    'btn_hover':    (0.200, 0.210, 0.290, 1.0),
    'btn_active':   (0.130, 0.520, 0.330, 1.0),
    'btn_active2':  (0.100, 0.400, 0.250, 1.0),
    # Grid
    'bg':           (0.095, 0.105, 0.145, 1.0),
    'bg_black':     (0.062, 0.068, 0.100, 1.0),
    'bg_c':         (0.115, 0.125, 0.172, 1.0),
    'grid':         (0.125, 0.135, 0.180, 1.0),
    'grid_beat':    (0.180, 0.192, 0.250, 1.0),
    'grid_bar':     (0.280, 0.295, 0.380, 1.0),
    'octave':       (0.220, 0.235, 0.310, 0.5),
    # Header
    'header':       (0.065, 0.070, 0.105, 1.0),
    'header_txt':   (0.520, 0.540, 0.640, 1.0),
    'header_bar':   (0.720, 0.740, 0.860, 1.0),
    # Piano keys
    'white_key':    (0.195, 0.205, 0.275, 1.0),
    'black_key':    (0.065, 0.068, 0.098, 1.0),
    'key_c':        (0.240, 0.255, 0.335, 1.0),
    'key_sep':      (0.140, 0.150, 0.200, 1.0),
    # Notes
    'note':         (0.120, 0.700, 0.400, 1.0),
    'note_top':     (0.200, 0.900, 0.540, 1.0),
    'note_dark':    (0.060, 0.340, 0.190, 1.0),
    'note_sel':     (0.380, 0.960, 0.640, 1.0),
    'note_sel_d':   (0.180, 0.580, 0.360, 1.0),
    'note_txt':     (0.020, 0.120, 0.060, 1.0),
    # Playhead
    'playhead':     (1.000, 0.800, 0.080, 1.0),
    'playhead_tri': (1.000, 0.870, 0.200, 1.0),
    # Velocity
    'vel_bg':       (0.055, 0.060, 0.090, 1.0),
    'vel_bar':      (0.120, 0.580, 0.340, 1.0),
    'vel_sel':      (0.360, 0.920, 0.580, 1.0),
    'vel_line':     (0.200, 0.210, 0.280, 1.0),
    # Scrollbar
    'sb_bg':        (0.090, 0.095, 0.135, 1.0),
    'sb_th':        (0.230, 0.245, 0.320, 1.0),
    # Misc
    'separator':    (0.220, 0.235, 0.310, 1.0),
    'text':         (0.720, 0.740, 0.840, 1.0),
    'text_dim':     (0.400, 0.415, 0.510, 1.0),
}

BLACK_NOTES = {1, 3, 6, 8, 10}
NOTE_NAMES  = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
SNAP_LABELS = {'1':'1/1','0.5':'1/2','0.25':'1/4','0.125':'1/8','0.0625':'1/16'}
TOOLS       = [('DRAW','D','Desenhar'),('SELECT','S','Selecionar'),
               ('ERASE','E','Apagar'),('PAN','P','Pan')]


# ═══════════════════════════════════════════════════════════════
#  DADOS
# ═══════════════════════════════════════════════════════════════

class MidiNote(bpy.types.PropertyGroup):
    pitch:    IntProperty(min=0, max=127)
    start:    FloatProperty()
    length:   FloatProperty()
    velocity: IntProperty(min=1, max=127, default=100)
    selected: BoolProperty(default=False)


class MidiStripData(bpy.types.PropertyGroup):
    strip_name: StringProperty()
    notes:      CollectionProperty(type=MidiNote)


class PianoRollState(bpy.types.PropertyGroup):
    notes:        CollectionProperty(type=MidiNote)     # fallback global
    zoom_x:       FloatProperty(default=1.0, min=0.1, max=8.0)
    zoom_y:       FloatProperty(default=1.0, min=0.3, max=4.0)
    scroll_x:     FloatProperty(default=0.0, min=0.0)
    scroll_y:     FloatProperty(default=48.0, min=0.0, max=127.0)
    snap_mode:    EnumProperty(
        items=[('1','1/1',''),('0.5','1/2',''),('0.25','1/4',''),
               ('0.125','1/8',''),('0.0625','1/16','')],
        default='0.25', name="Snap")
    active_track: IntProperty(default=0)
    total_beats:  FloatProperty(default=32.0)
    active_strip: StringProperty(default="")
    midi_strips:  CollectionProperty(type=MidiStripData)
    tool:         EnumProperty(
        items=[('DRAW','Desenhar',''),('SELECT','Selecionar',''),
               ('ERASE','Apagar',''),('PAN','Pan','')],
        default='DRAW', name="Ferramenta")
    show_velocity: BoolProperty(default=True, name="Velocity")


def _get_active_notes(state):
    if state.active_strip:
        for ms in state.midi_strips:
            if ms.strip_name == state.active_strip:
                return ms.notes
    return state.notes


# ═══════════════════════════════════════════════════════════════
#  HELPERS DE DESENHO
# ═══════════════════════════════════════════════════════════════

_shader = None

def _sh():
    global _shader
    if _shader is None:
        _shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    return _shader

def _rect(x, y, w, h, col):
    if w <= 0 or h <= 0:
        return
    s = _sh()
    b = batch_for_shader(s,'TRIS',{"pos":[
        (x,y),(x+w,y),(x+w,y+h),(x,y),(x+w,y+h),(x,y+h)]})
    s.uniform_float("color", col); b.draw(s)

def _rect_border(x, y, w, h, col, border_col, bw=1):
    _rect(x, y, w, h, col)
    _rect(x, y+h-bw, w, bw, border_col)

def _line(x1, y1, x2, y2, col):
    s = _sh()
    b = batch_for_shader(s,'LINES',{"pos":[(x1,y1),(x2,y2)]})
    s.uniform_float("color", col); b.draw(s)

def _tri(pts, col):
    s = _sh()
    b = batch_for_shader(s,'TRIS',{"pos": pts})
    s.uniform_float("color", col); b.draw(s)

def _txt(text, x, y, size, col):
    blf.size(0, size); blf.color(0, *col)
    blf.position(0, x, y, 0); blf.draw(0, text)

def _note_name(m): return f"{NOTE_NAMES[m%12]}{m//12-1}"
def _is_black(m):  return (m%12) in BLACK_NOTES


# ═══════════════════════════════════════════════════════════════
#  CÁLCULO DE LAYOUT
# ═══════════════════════════════════════════════════════════════

def _layout(W, H, state):
    vel_h   = VELOCITY_H if state.show_velocity else 0
    grid_y  = SCROLLBAR
    grid_y += vel_h
    grid_y += 0  # separator
    header_y = H - TOOLBAR_H - HEADER_H
    grid_h   = header_y - grid_y
    grid_x   = PIANO_W
    grid_w   = W - PIANO_W - SCROLLBAR
    return {
        'grid_x': grid_x, 'grid_y': grid_y,
        'grid_w': grid_w, 'grid_h': grid_h,
        'header_y': header_y,
        'vel_h': vel_h,
        'toolbar_y': H - TOOLBAR_H,
    }


# ═══════════════════════════════════════════════════════════════
#  DRAW — PIANO ROLL COMPLETO
# ═══════════════════════════════════════════════════════════════

def _draw_piano_roll(context):
    state  = context.scene.piano_roll
    region = context.region
    W, H   = region.width, region.height

    L = _layout(W, H, state)
    gx, gy    = L['grid_x'], L['grid_y']
    gw, gh    = L['grid_w'], L['grid_h']
    vel_h     = L['vel_h']
    toolbar_y = L['toolbar_y']
    header_y  = L['header_y']

    note_h = NOTE_H_BASE * state.zoom_y
    beat_w = BEAT_W_BASE  * state.zoom_x
    snap   = float(state.snap_mode)

    vis_notes = int(gh / note_h) + 2
    top_note  = min(int(state.scroll_y + vis_notes / 2), 127)

    gpu.state.blend_set('ALPHA')

    # ── Fundo geral ──────────────────────────────────────────
    _rect(0, 0, W, H, C['bg'])

    # ══ GRID DE NOTAS ════════════════════════════════════════
    for i in range(vis_notes + 1):
        note = top_note - i
        if not 0 <= note <= 127:
            continue
        ny = gy + gh - (i + 1) * note_h + (state.scroll_y % 1) * note_h
        if note % 12 == 0:
            col = C['bg_c']
        elif _is_black(note):
            col = C['bg_black']
        else:
            col = C['bg']
        _rect(gx, ny, gw, note_h - 0.5, col)
        if note % 12 == 0:
            _line(gx, ny + note_h, gx + gw, ny + note_h, C['octave'])

    # ══ GRID VERTICAL (beats / compassos) ════════════════════
    b = 0
    while True:
        bx = gx + b * beat_w * snap / snap - (state.scroll_x % snap) * beat_w
        if bx > gx + gw:
            break
        beat_abs = state.scroll_x + b * snap
        is_bar   = abs(beat_abs % 4) < 0.001
        if bx >= gx:
            col = C['grid_bar'] if is_bar else (
                  C['grid_beat'] if abs(beat_abs % 1) < 0.001 else C['grid'])
            _line(bx, gy, bx, gy + gh, col)
        b += 1
        if b > 4000:
            break

    # ══ NOTAS MIDI ════════════════════════════════════════════
    notes = _get_active_notes(state)
    for note in notes:
        ni  = top_note - note.pitch
        ny  = gy + gh - (ni + 1) * note_h + (state.scroll_y % 1) * note_h
        if ny + note_h < gy or ny > gy + gh:
            continue
        nx  = gx + (note.start - state.scroll_x) * beat_w
        nw  = max(note.length * beat_w - 1, 3)
        if nx + nw < gx or nx > gx + gw:
            continue
        nx2 = max(nx, gx)
        nw2 = nw - (nx2 - nx)
        if nw2 <= 0:
            continue

        if note.selected:
            body  = C['note_sel']
            top   = C['note_sel']
            dark  = C['note_sel_d']
        else:
            body  = C['note']
            top   = C['note_top']
            dark  = C['note_dark']

        _rect(nx2, ny + 1, nw2, note_h - 2, body)
        # Borda superior brilhante
        _rect(nx2, ny + note_h - 3, nw2, 2, top)
        # Borda inferior escura
        _rect(nx2, ny + 1, nw2, 2, dark)
        # Nome da nota
        if nw2 > 22 and note_h > 10:
            _txt(_note_name(note.pitch), nx2 + 3, ny + 3, 9, C['note_txt'])

    # ══ PLAYHEAD ═════════════════════════════════════════════
    ph_beat = _get_playhead_beat(context)
    ph_x    = gx + (ph_beat - state.scroll_x) * beat_w
    if gx <= ph_x <= gx + gw:
        _rect(ph_x - 1, gy, 2, gh, C['playhead'])
        # Triângulo no header
        _tri([(ph_x - 7, header_y + HEADER_H),
              (ph_x + 7, header_y + HEADER_H),
              (ph_x,     header_y + HEADER_H - 10)], C['playhead_tri'])

    # ══ PIANO KEYS (lateral esquerda) ════════════════════════
    _rect(0, gy, PIANO_W, gh, (0.058, 0.062, 0.092, 1.0))
    for i in range(vis_notes + 1):
        note = top_note - i
        if not 0 <= note <= 127:
            continue
        ny = gy + gh - (i + 1) * note_h + (state.scroll_y % 1) * note_h
        is_b = _is_black(note)
        if note % 12 == 0:
            col = C['key_c']
        elif is_b:
            col = C['black_key']
        else:
            col = C['white_key']
        pw = PIANO_W - 5 if is_b else PIANO_W - 1
        _rect(1, ny + 0.5, pw, note_h - 1, col)
        # Separador inferior nas teclas brancas
        if not is_b:
            _line(1, ny, pw + 1, ny, C['key_sep'])
        # Label C
        if note % 12 == 0 and note_h > 9:
            _txt(_note_name(note), 3, ny + 2, 8, C['text_dim'])
    # Borda direita do piano
    _line(PIANO_W, gy, PIANO_W, gy + gh, C['separator'])

    # ══ HEADER — marcadores de compasso ══════════════════════
    _rect(0, header_y, W, HEADER_H, C['header'])
    _rect(gx, header_y, gw, HEADER_H, C['header'])
    b = 0
    while True:
        bx = gx + b * beat_w - (state.scroll_x % 1) * beat_w
        if bx > gx + gw:
            break
        beat_abs = state.scroll_x + b
        if bx >= gx and abs(beat_abs % 4) < 0.001:
            bar = int(beat_abs / 4) + 1
            _txt(str(bar), bx + 3, header_y + 6, 11, C['header_bar'])
            _line(bx, header_y, bx, header_y + HEADER_H, C['grid_bar'])
        elif bx >= gx and abs(beat_abs % 1) < 0.001:
            _line(bx, header_y, bx, header_y + HEADER_H // 2, C['grid'])
        b += 1
        if b > 4000:
            break
    # Playhead no header
    if gx <= ph_x <= gx + gw:
        _rect(ph_x - 1, header_y, 2, HEADER_H, C['playhead'])

    # ══ VELOCITY LANE ════════════════════════════════════════
    if vel_h > 0:
        sep_y = SCROLLBAR + vel_h
        _rect(0, SCROLLBAR, W, vel_h, C['vel_bg'])
        _line(0, sep_y, W, sep_y, C['separator'])
        _line(gx, SCROLLBAR, gx, sep_y, C['separator'])
        _txt("VEL", 4, SCROLLBAR + vel_h // 2 - 5, 9, C['text_dim'])

        for note in notes:
            nx = gx + (note.start - state.scroll_x) * beat_w
            nw = max(note.length * beat_w * 0.6, 4)
            if nx + nw < gx or nx > gx + gw:
                continue
            nx2 = max(nx, gx)
            nw2 = nw - (nx2 - nx)
            if nw2 <= 0:
                continue
            bh = max(int((note.velocity / 127.0) * (vel_h - 8)), 2)
            col = C['vel_sel'] if note.selected else C['vel_bar']
            _rect(nx2 + 1, SCROLLBAR + 2, max(nw2 - 2, 2), bh, col)

        # Linha de 100% velocity
        full_y = SCROLLBAR + vel_h - 4
        _line(gx, full_y, gx + gw, full_y, C['vel_line'])

    # ══ TOOLBAR ══════════════════════════════════════════════
    _rect(0, toolbar_y, W, TOOLBAR_H, C['toolbar'])
    _line(0, toolbar_y, W, toolbar_y, C['separator'])

    # Botões de ferramenta
    btn_w, btn_h, btn_pad = 52, 22, 5
    bx0 = PIANO_W + 8
    for i, (tid, tlabel, ttip) in enumerate(TOOLS):
        bx   = bx0 + i * (btn_w + 4)
        by   = toolbar_y + (TOOLBAR_H - btn_h) // 2
        is_a = state.tool == tid
        col  = C['btn_active'] if is_a else C['btn']
        _rect(bx, by, btn_w, btn_h, col)
        if is_a:
            _rect(bx, by, btn_w, 2, C['btn_active2'])
        tc = C['white'] if is_a else C['text_dim']
        _txt(f"{tlabel[0]}  {ttip[:3]}", bx + 6, by + 6, 10, tc)

    # Snap buttons
    sx0 = bx0 + len(TOOLS) * (btn_w + 4) + 16
    for i, (sval, slbl) in enumerate([('1','1/1'),('0.5','1/2'),
                                       ('0.25','1/4'),('0.125','1/8'),
                                       ('0.0625','1/16')]):
        sx   = sx0 + i * 42
        sy   = toolbar_y + (TOOLBAR_H - btn_h) // 2
        is_a = state.snap_mode == sval
        col  = C['btn_active'] if is_a else C['btn']
        _rect(sx, sy, 38, btn_h, col)
        tc = C['white'] if is_a else C['text_dim']
        _txt(slbl, sx + 4, sy + 6, 9, tc)

    # VEL toggle
    vtx  = sx0 + 5 * 42 + 12
    vty  = toolbar_y + (TOOLBAR_H - btn_h) // 2
    vcol = C['btn_active'] if state.show_velocity else C['btn']
    _rect(vtx, vty, 40, btn_h, vcol)
    tc = C['white'] if state.show_velocity else C['text_dim']
    _txt("VEL", vtx + 10, vty + 6, 10, tc)

    # Titulo strip ativo
    strip_label = state.active_strip or "—"
    _txt(f"  {strip_label}", 4, toolbar_y + 10, 11, C['text'])

    # ESC hint
    _txt("ESC: fechar", W - 80, toolbar_y + 10, 9, C['text_dim'])

    # ══ SCROLLBARS ═══════════════════════════════════════════
    # Horizontal
    _rect(gx, 0, gw, SCROLLBAR - 1, C['sb_bg'])
    tw  = max(gw * (gw / max(state.total_beats * beat_w, gw + 1)), 20)
    tx  = gx + (state.scroll_x / max(state.total_beats, 1)) * (gw - tw)
    _rect(tx, 1, tw, SCROLLBAR - 3, C['sb_th'])

    # Vertical
    _rect(W - SCROLLBAR, gy, SCROLLBAR - 1, gh, C['sb_bg'])
    th  = max(gh * (vis_notes / TOTAL_NOTES), 20)
    ty  = gy + gh - (state.scroll_y / 127.0) * (gh - th) - th
    _rect(W - SCROLLBAR + 1, ty, SCROLLBAR - 3, th, C['sb_th'])

    gpu.state.blend_set('NONE')


def _get_playhead_beat(context):
    try:
        from .register import get_engine
        e = get_engine()
        if e and e.running:
            s = e.get_state()
            if s:
                return s.position_beats
    except Exception:
        pass
    fps = context.scene.render.fps
    bpm = 120.0
    return (context.scene.frame_current / fps) * (bpm / 60.0)


# ═══════════════════════════════════════════════════════════════
#  MODAL — HIT TEST TOOLBAR
# ═══════════════════════════════════════════════════════════════

def _toolbar_hit(mx, my, W, H, state):
    """Retorna (tipo, valor) se o clique foi na toolbar."""
    L = _layout(W, H, state)
    toolbar_y = L['toolbar_y']
    if my < toolbar_y:
        return None, None

    btn_w, btn_h, btn_pad = 52, 22, 5
    bx0 = PIANO_W + 8
    for i, (tid, tlabel, ttip) in enumerate(TOOLS):
        bx = bx0 + i * (btn_w + 4)
        by = toolbar_y + (TOOLBAR_H - btn_h) // 2
        if bx <= mx <= bx + btn_w and by <= my <= by + btn_h:
            return 'TOOL', tid

    sx0 = bx0 + len(TOOLS) * (btn_w + 4) + 16
    for i, sval in enumerate(['1','0.5','0.25','0.125','0.0625']):
        sx = sx0 + i * 42
        sy = toolbar_y + (TOOLBAR_H - btn_h) // 2
        if sx <= mx <= sx + 38 and sy <= my <= sy + btn_h:
            return 'SNAP', sval

    vtx = sx0 + 5 * 42 + 12
    vty = toolbar_y + (TOOLBAR_H - btn_h) // 2
    if vtx <= mx <= vtx + 40 and vty <= my <= vty + btn_h:
        return 'VEL', None

    return 'TOOLBAR', None


# ═══════════════════════════════════════════════════════════════
#  MODAL OPERATOR
# ═══════════════════════════════════════════════════════════════

class DAW_OT_PianoRollModal(bpy.types.Operator):
    bl_idname  = "daw.piano_roll_modal"
    bl_label   = "Piano Roll"
    bl_options = {'REGISTER'}

    _handle          = None
    _dragging        = False
    _drag_mode       = None
    _active_note_idx = -1
    _last_x = _last_y = 0

    # ── conversões px → musica ─────────────────────────────

    def _beat(self, x, state, region):
        L = _layout(region.width, region.height, state)
        return state.scroll_x + (x - L['grid_x']) / (BEAT_W_BASE * state.zoom_x)

    def _pitch(self, y, state, region):
        L    = _layout(region.width, region.height, state)
        nh   = NOTE_H_BASE * state.zoom_y
        vis  = L['grid_h'] / nh
        top  = int(state.scroll_y + vis / 2)
        idx  = int((L['grid_y'] + L['grid_h'] - y) / nh)
        return top - idx

    def _snap(self, beat, state):
        s = float(state.snap_mode)
        return round(beat / s) * s

    def _in_grid(self, mx, my, region, state):
        L = _layout(region.width, region.height, state)
        return (L['grid_x'] <= mx <= region.width - SCROLLBAR and
                L['grid_y'] <= my <= L['grid_y'] + L['grid_h'])

    def _in_vel(self, mx, my, state, region):
        if not state.show_velocity:
            return False
        L = _layout(region.width, region.height, state)
        return (L['grid_x'] <= mx <= region.width - SCROLLBAR and
                SCROLLBAR <= my <= SCROLLBAR + L['vel_h'])

    # ── CRUD notas ─────────────────────────────────────────

    def _find(self, beat, pitch, state):
        for i, n in enumerate(_get_active_notes(state)):
            if n.pitch == pitch and n.start <= beat < n.start + n.length:
                return i
        return -1

    def _add(self, beat, pitch, state):
        sn = self._snap(beat, state)
        if self._find(sn, pitch, state) >= 0:
            return -1
        notes = _get_active_notes(state)
        n = notes.add()
        n.pitch = max(0, min(127, pitch))
        n.start = max(0, sn)
        n.length = float(state.snap_mode)
        n.velocity = 100
        return len(notes) - 1

    def _remove(self, beat, pitch, state):
        idx = self._find(beat, pitch, state)
        if idx >= 0:
            _get_active_notes(state).remove(idx)

    def _select_all(self, state, val):
        for n in _get_active_notes(state):
            n.selected = val

    # ── invoke ─────────────────────────────────────────────

    def invoke(self, context, event):
        if context.area.type != 'VIEW_3D':
            self.report({'WARNING'}, "Precisa de área VIEW_3D")
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
        W, H   = region.width, region.height
        L      = _layout(W, H, state)

        beat_w = BEAT_W_BASE * state.zoom_x
        note_h = NOTE_H_BASE * state.zoom_y

        # ESC
        if event.type == 'ESC':
            self._cleanup(context)
            return {'FINISHED'}

        # Scroll
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

        # Teclas snap
        snap_map = {'ONE':'1','TWO':'0.5','THREE':'0.25','FOUR':'0.125','FIVE':'0.0625'}
        if event.type in snap_map and event.value == 'PRESS':
            state.snap_mode = snap_map[event.type]
            return {'RUNNING_MODAL'}

        # Teclas ferramenta
        tool_map = {'D':'DRAW','S':'SELECT','E':'ERASE','P':'PAN'}
        if event.type in tool_map and event.value == 'PRESS':
            state.tool = tool_map[event.type]
            return {'RUNNING_MODAL'}

        # Ctrl+A seleciona tudo
        if event.type == 'A' and event.ctrl and event.value == 'PRESS':
            self._select_all(state, True)
            return {'RUNNING_MODAL'}

        # Delete apaga selecionadas
        if event.type in ('DEL','X') and event.value == 'PRESS':
            notes = _get_active_notes(state)
            for i in range(len(notes) - 1, -1, -1):
                if notes[i].selected:
                    notes.remove(i)
            return {'RUNNING_MODAL'}

        # MMB — pan
        if event.type == 'MIDDLEMOUSE':
            if event.value == 'PRESS':
                self._dragging = True; self._drag_mode = 'PAN'
                self._last_x, self._last_y = mx, my
            else:
                self._dragging = False; self._drag_mode = None
            return {'RUNNING_MODAL'}

        if self._dragging and self._drag_mode == 'PAN' and event.type == 'MOUSEMOVE':
            state.scroll_x = max(0, state.scroll_x - (mx - self._last_x) / beat_w)
            state.scroll_y = max(0, min(127, state.scroll_y + (my - self._last_y) / note_h))
            self._last_x, self._last_y = mx, my
            return {'RUNNING_MODAL'}

        # LMB
        if event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                # ── Toolbar click ─────────────────────────
                typ, val = _toolbar_hit(mx, my, W, H, state)
                if typ == 'TOOL': state.tool = val; return {'RUNNING_MODAL'}
                if typ == 'SNAP': state.snap_mode = val; return {'RUNNING_MODAL'}
                if typ == 'VEL':  state.show_velocity = not state.show_velocity; return {'RUNNING_MODAL'}
                if typ == 'TOOLBAR': return {'RUNNING_MODAL'}

                beat  = self._beat(mx, state, region)
                pitch = self._pitch(my, state, region)

                # ── Velocity lane ─────────────────────────
                if self._in_vel(mx, my, state, region):
                    notes = _get_active_notes(state)
                    vel_h = L['vel_h']
                    new_vel = int(((my - SCROLLBAR) / max(vel_h, 1)) * 127)
                    new_vel = max(1, min(127, new_vel))
                    for n in notes:
                        nx = L['grid_x'] + (n.start - state.scroll_x) * beat_w
                        nw = n.length * beat_w
                        if nx <= mx <= nx + nw:
                            n.velocity = new_vel
                    self._dragging = True; self._drag_mode = 'VELOCITY'
                    return {'RUNNING_MODAL'}

                # ── Grid click ────────────────────────────
                if self._in_grid(mx, my, region, state):
                    if state.tool == 'DRAW':
                        self._drag_mode = 'NOTE_DRAW'
                        self._active_note_idx = self._add(beat, pitch, state)
                        self._dragging = True
                    elif state.tool == 'SELECT':
                        self._drag_mode = 'NOTE_SELECT'
                        if not event.shift:
                            self._select_all(state, False)
                        idx = self._find(beat, pitch, state)
                        if idx >= 0:
                            _get_active_notes(state)[idx].selected = True
                        self._dragging = True
                    elif state.tool == 'ERASE':
                        self._remove(beat, pitch, state)
                        self._drag_mode = 'NOTE_ERASE'
                        self._dragging = True
                    elif state.tool == 'PAN':
                        self._dragging = True; self._drag_mode = 'PAN'
                    self._last_x, self._last_y = mx, my

            elif event.value == 'RELEASE':
                self._dragging = False; self._drag_mode = None; self._active_note_idx = -1
            return {'RUNNING_MODAL'}

        # Mouse move — arrasto
        if event.type == 'MOUSEMOVE' and self._dragging:
            beat  = self._beat(mx, state, region)
            pitch = self._pitch(my, state, region)

            if self._drag_mode == 'NOTE_DRAW':
                notes = _get_active_notes(state)
                if 0 <= self._active_note_idx < len(notes):
                    n = notes[self._active_note_idx]
                    snap = float(state.snap_mode)
                    n.length = max(snap, self._snap(beat - n.start + snap, state))

            elif self._drag_mode == 'NOTE_ERASE':
                self._remove(beat, pitch, state)

            elif self._drag_mode == 'PAN':
                state.scroll_x = max(0, state.scroll_x - (mx - self._last_x) / beat_w)
                state.scroll_y = max(0, min(127, state.scroll_y + (my - self._last_y) / note_h))
                self._last_x, self._last_y = mx, my

            return {'RUNNING_MODAL'}

        # RMB apaga
        if event.type == 'RIGHTMOUSE' and event.value == 'PRESS':
            if self._in_grid(mx, my, region, state):
                self._remove(self._beat(mx, state, region),
                             self._pitch(my, state, region), state)
            return {'RUNNING_MODAL'}

        return {'PASS_THROUGH'}

    def _cleanup(self, context):
        if self._handle:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            self._handle = None
        context.area.tag_redraw()


# ═══════════════════════════════════════════════════════════════
#  ABRIR COMO JANELA FLUTUANTE
# ═══════════════════════════════════════════════════════════════

class DAW_OT_OpenPianoRoll(bpy.types.Operator):
    bl_idname      = "daw.open_piano_roll"
    bl_label       = "Abrir Piano Roll"
    bl_description = "Abre o Piano Roll em janela flutuante"

    def execute(self, context):
        # Guarda referência antes de qualquer troca
        cur_window = context.window
        cur_area   = context.area

        # Abre nova janela do Blender
        bpy.ops.wm.window_new()

        def _setup():
            try:
                wm      = bpy.context.window_manager
                new_win = wm.windows[-1]

                # Configura a primeira área da nova janela como VIEW_3D
                for area in new_win.screen.areas:
                    area.type = 'VIEW_3D'
                    for sp in area.spaces:
                        if sp.type == 'VIEW_3D':
                            sp.overlay.show_overlays = False
                            sp.show_gizmo            = False
                            sp.shading.type          = 'SOLID'

                    win_reg = next((r for r in area.regions
                                    if r.type == 'WINDOW'), None)
                    if win_reg:
                        with bpy.context.temp_override(
                                window=new_win, area=area, region=win_reg):
                            bpy.ops.daw.piano_roll_modal('INVOKE_DEFAULT')
                        print("[DAW] Piano Roll aberto em janela flutuante ✅")
                    break

            except Exception as e:
                print(f"[DAW] Janela flutuante falhou ({e}), abrindo na área atual...")
                # Fallback: abre no VIEW_3D da janela atual
                try:
                    for area in cur_window.screen.areas:
                        if area.type == 'VIEW_3D':
                            win_reg = next((r for r in area.regions
                                            if r.type == 'WINDOW'), None)
                            if win_reg:
                                with bpy.context.temp_override(
                                        window=cur_window, area=area,
                                        region=win_reg):
                                    bpy.ops.daw.piano_roll_modal('INVOKE_DEFAULT')
                            break
                    else:
                        # Último recurso: converte a área atual
                        cur_area.type = 'VIEW_3D'
                        for sp in cur_area.spaces:
                            if sp.type == 'VIEW_3D':
                                sp.overlay.show_overlays = False
                                sp.show_gizmo = False
                        win_reg = next((r for r in cur_area.regions
                                        if r.type == 'WINDOW'), None)
                        if win_reg:
                            with bpy.context.temp_override(
                                    window=cur_window, area=cur_area,
                                    region=win_reg):
                                bpy.ops.daw.piano_roll_modal('INVOKE_DEFAULT')
                except Exception as e2:
                    print(f"[DAW] Fallback também falhou: {e2}")
            return None

        bpy.app.timers.register(_setup, first_interval=0.25)
        return {'FINISHED'}


# ═══════════════════════════════════════════════════════════════
#  NOVA TRACK MIDI
# ═══════════════════════════════════════════════════════════════

class DAW_OT_NewMidiStrip(bpy.types.Operator):
    bl_idname      = "daw.new_midi_strip"
    bl_label       = "Nova Track MIDI"
    bl_description = "Cria strip MIDI no Sequencer e abre o Piano Roll"

    def execute(self, context):
        scene = context.scene
        state = scene.piano_roll
        seq   = scene.sequence_editor_create()

        used = {s.channel for s in seq.sequences_all}
        ch   = 1
        while ch in used:
            ch += 1

        idx   = len(state.midi_strips) + 1
        name  = f"MIDI {idx:02d}"
        start = scene.frame_current
        end   = start + scene.render.fps * 4

        strip = seq.sequences.new_effect(
            name=name, type='COLOR', channel=ch,
            frame_start=start, frame_end=end)
        strip.color = (0.08, 0.45, 0.26)

        ms = state.midi_strips.add()
        ms.strip_name = name
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


class DAW_OT_ClearNotes(bpy.types.Operator):
    bl_idname = "daw.clear_notes"
    bl_label  = "Limpar Notas"
    def execute(self, context):
        _get_active_notes(context.scene.piano_roll).clear()
        return {'FINISHED'}


# ═══════════════════════════════════════════════════════════════
#  TIMER REDRAW
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
    bl_label       = "Piano Roll"
    bl_idname      = "DAW_PT_piano_roll"
    bl_space_type  = 'SEQUENCE_EDITOR'
    bl_region_type = 'UI'
    bl_category    = "DAW"
    bl_order       = 1

    def draw(self, context):
        layout = self.layout
        state  = context.scene.piano_roll

        layout.operator("daw.new_midi_strip", icon='ADD', text="Nova Track MIDI")
        layout.separator()

        if len(state.midi_strips) > 0:
            box = layout.box()
            box.label(text="Tracks MIDI:", icon='SEQUENCE')
            for ms in state.midi_strips:
                row = box.row(align=True)
                is_a = ms.strip_name == state.active_strip
                op = row.operator("daw.select_midi_strip",
                                  text=ms.strip_name,
                                  icon='PLAY' if is_a else 'DOT')
                op.strip_name = ms.strip_name
                row.label(text=f"{len(ms.notes)} notas")
            layout.separator()

        layout.operator("daw.open_piano_roll", icon='PIANO',
                        text="Abrir Piano Roll ↗")
        layout.separator()

        box2 = layout.box()
        box2.label(text="Controles rápidos", icon='INFO')
        col = box2.column(align=True)
        col.scale_y = 0.75
        col.label(text="D/S/E/P: Ferramenta")
        col.label(text="1-5: Snap")
        col.label(text="Ctrl+Scroll: Zoom X")
        col.label(text="Shift+Scroll: Zoom Y")
        col.label(text="MMB: Pan  |  ESC: Fechar")
        col.label(text="Del: Apagar selecionadas")

        notes = _get_active_notes(state)
        if len(notes) > 0:
            layout.separator()
            layout.operator("daw.clear_notes", icon='TRASH',
                            text=f"Limpar {len(notes)} notas")


# ═══════════════════════════════════════════════════════════════
#  REGISTRO
# ═══════════════════════════════════════════════════════════════

classes = [
    MidiNote, MidiStripData, PianoRollState,
    DAW_OT_PianoRollModal, DAW_OT_OpenPianoRoll,
    DAW_OT_NewMidiStrip, DAW_OT_SelectMidiStrip,
    DAW_OT_ClearNotes, DAW_PT_PianoRoll,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.piano_roll = bpy.props.PointerProperty(type=PianoRollState)
    if not bpy.app.timers.is_registered(_sync_playhead):
        bpy.app.timers.register(_sync_playhead, persistent=True)


def unregister():
    if bpy.app.timers.is_registered(_sync_playhead):
        bpy.app.timers.unregister(_sync_playhead)
    del bpy.types.Scene.piano_roll
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
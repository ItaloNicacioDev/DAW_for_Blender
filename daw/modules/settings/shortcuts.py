# modules/settings/shortcuts.py
"""
Gerenciador de atalhos de teclado (keymaps) para o addon DAW.

Define keymaps padrão e permite customização via preferências.
"""
from __future__ import annotations

import bpy
from bpy.types import KeyMapItem


# ============================================================================
# MAPA DE ATALHOS PADRÃO
# ============================================================================

DEFAULT_SHORTCUTS = {
    # Playback
    'daw.play_pause': {
        'type': 'SPACE',
        'value': 'PRESS',
        'ctrl': False,
        'shift': False,
        'alt': False,
        'oskey': False,
        'repeat': False,
    },
    'daw.stop': {
        'type': 'SPACE',
        'value': 'PRESS',
        'ctrl': False,
        'shift': True,
        'alt': False,
        'oskey': False,
        'repeat': False,
    },
    'daw.record': {
        'type': 'R',
        'value': 'PRESS',
        'ctrl': True,
        'shift': False,
        'alt': False,
        'oskey': False,
        'repeat': False,
    },
    
    # Editing
    'daw.undo': {
        'type': 'Z',
        'value': 'PRESS',
        'ctrl': True,
        'shift': False,
        'alt': False,
        'oskey': False,
        'repeat': False,
    },
    'daw.redo': {
        'type': 'Z',
        'value': 'PRESS',
        'ctrl': True,
        'shift': True,
        'alt': False,
        'oskey': False,
        'repeat': False,
    },
    'daw.delete': {
        'type': 'X',
        'value': 'PRESS',
        'ctrl': False,
        'shift': False,
        'alt': False,
        'oskey': False,
        'repeat': False,
    },
    
    # Selection
    'daw.select_all': {
        'type': 'A',
        'value': 'PRESS',
        'ctrl': True,
        'shift': False,
        'alt': False,
        'oskey': False,
        'repeat': False,
    },
    'daw.deselect_all': {
        'type': 'A',
        'value': 'PRESS',
        'ctrl': True,
        'shift': True,
        'alt': False,
        'oskey': False,
        'repeat': False,
    },
    
    # Zoom
    'daw.zoom_in': {
        'type': 'EQUAL',
        'value': 'PRESS',
        'ctrl': True,
        'shift': False,
        'alt': False,
        'oskey': False,
        'repeat': False,
    },
    'daw.zoom_out': {
        'type': 'MINUS',
        'value': 'PRESS',
        'ctrl': True,
        'shift': False,
        'alt': False,
        'oskey': False,
        'repeat': False,
    },
    'daw.zoom_fit': {
        'type': 'ZERO',
        'value': 'PRESS',
        'ctrl': True,
        'shift': False,
        'alt': False,
        'oskey': False,
        'repeat': False,
    },
    
    # Transport
    'daw.rewind': {
        'type': 'LEFT_ARROW',
        'value': 'PRESS',
        'ctrl': False,
        'shift': False,
        'alt': False,
        'oskey': False,
        'repeat': True,
    },
    'daw.forward': {
        'type': 'RIGHT_ARROW',
        'value': 'PRESS',
        'ctrl': False,
        'shift': False,
        'alt': False,
        'oskey': False,
        'repeat': True,
    },
    'daw.jump_to_start': {
        'type': 'HOME',
        'value': 'PRESS',
        'ctrl': False,
        'shift': False,
        'alt': False,
        'oskey': False,
        'repeat': False,
    },
    'daw.jump_to_end': {
        'type': 'END',
        'value': 'PRESS',
        'ctrl': False,
        'shift': False,
        'alt': False,
        'oskey': False,
        'repeat': False,
    },
}


# ============================================================================
# REGISTRO DE KEYMAPS
# ============================================================================

_addon_keymaps = []


def register_keymaps():
    """Registra todos os keymaps do addon."""
    wm = bpy.context.window_manager
    
    # Encontra ou cria o keymap para a space de properties
    kc = wm.keyconfigs.addon
    if not kc:
        return
    
    km = kc.keymaps.new(name="Properties", space_type='PROPERTIES')
    
    # Registra cada atalho
    for op_id, keymap_def in DEFAULT_SHORTCUTS.items():
        kmi = km.keymap_items.new(
            idname=op_id,
            type=keymap_def['type'],
            value=keymap_def['value'],
            ctrl=keymap_def['ctrl'],
            shift=keymap_def['shift'],
            alt=keymap_def['alt'],
            oskey=keymap_def['oskey'],
            repeat=keymap_def['repeat'],
        )
        _addon_keymaps.append((km, kmi))


def unregister_keymaps():
    """Desregistra todos os keymaps do addon."""
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    
    for km, kmi in _addon_keymaps:
        km.keymap_items.remove(kmi)
    
    _addon_keymaps.clear()


def reset_keymaps_to_default():
    """Reseta keymaps para os padrões."""
    unregister_keymaps()
    register_keymaps()


def customize_keymap(op_id: str, key_type: str, value: str = 'PRESS',
                     ctrl: bool = False, shift: bool = False,
                     alt: bool = False, oskey: bool = False):
    """Customiza um atalho específico.
    
    Args:
        op_id: ID do operador (ex: 'daw.play_pause')
        key_type: Tipo de tecla (ex: 'SPACE', 'P', etc)
        value: Tipo de evento (PRESS, RELEASE, etc)
        ctrl, shift, alt, oskey: Modificadores
    """
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    
    if not kc:
        return False
    
    km = kc.keymaps.get("Properties")
    if not km:
        return False
    
    # Remove keymap antigo
    for kmi in km.keymap_items:
        if kmi.idname == op_id:
            km.keymap_items.remove(kmi)
            break
    
    # Cria novo
    km.keymap_items.new(
        idname=op_id,
        type=key_type,
        value=value,
        ctrl=ctrl,
        shift=shift,
        alt=alt,
        oskey=oskey,
    )
    
    return True


def get_shortcut(op_id: str) -> str | None:
    """Retorna a combinação de teclas para um operador.
    
    Formato: "SPACE", "CTRL+P", "SHIFT+SPACE", etc
    """
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    
    if not kc:
        return None
    
    km = kc.keymaps.get("Properties")
    if not km:
        return None
    
    for kmi in km.keymap_items:
        if kmi.idname == op_id:
            parts = []
            if kmi.ctrl:
                parts.append("CTRL")
            if kmi.shift:
                parts.append("SHIFT")
            if kmi.alt:
                parts.append("ALT")
            if kmi.oskey:
                parts.append("OSKEY")
            
            parts.append(kmi.type)
            return "+".join(parts)
    
    return None


def get_all_shortcuts() -> dict[str, str]:
    """Retorna todos os atalhos registrados."""
    shortcuts = {}
    for op_id in DEFAULT_SHORTCUTS.keys():
        shortcut = get_shortcut(op_id)
        if shortcut:
            shortcuts[op_id] = shortcut
    return shortcuts


classes = []


def register():
    """Registra keymaps."""
    try:
        register_keymaps()
    except Exception as e:
        print(f"Erro ao registrar keymaps: {e}")


def unregister():
    """Desregistra keymaps."""
    try:
        unregister_keymaps()
    except Exception as e:
        print(f"Erro ao desregistrar keymaps: {e}")
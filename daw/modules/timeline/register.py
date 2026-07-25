"""
timeline/register.py
Registro e desregistro centralizados de todos os componentes do módulo timeline.
Ordem importa: properties deve ser o primeiro (outros dependem das classes registradas).
"""

from . import properties, operators, ui


def register():
    """Registra todos os componentes da timeline."""
    properties.register()   # PropertyGroups e bpy.types.Scene.daw_timeline
    operators.register()    # Todos os bpy.types.Operator
    ui.register()           # Painéis e draw handler


def unregister():
    """Desregistra em ordem inversa."""
    ui.unregister()
    operators.unregister()
    properties.unregister()
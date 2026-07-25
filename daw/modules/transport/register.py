"""transport/register.py

Ponto único de registro/desregistro do módulo `transport`. Chame
`transport.register()` / `transport.unregister()` a partir do
`register()`/`unregister()` do addon principal.

Ordem importa:
1. properties  -> precisa existir antes de qualquer operador/painel
   que leia `scene.daw_transport`.
2. operators   -> play/pause/stop/record (core)
3. bpm/tempo   -> tap tempo + dobrar/reduzir tempo
4. loop        -> handler de loop + operadores de região
5. ui          -> painel, depende de tudo acima já estar registrado
"""

import bpy

from . import properties
from . import operators
from . import bpm
from . import tempo
from . import loop
from . import ui


_MODULES_WITH_REGISTER = (properties, operators, loop, ui)
_MODULE_CLASS_LISTS = (bpm.classes, tempo.classes)


def register():
    for module in _MODULES_WITH_REGISTER:
        module.register()
    for classes in _MODULE_CLASS_LISTS:
        for cls in classes:
            bpy.utils.register_class(cls)


def unregister():
    for classes in reversed(_MODULE_CLASS_LISTS):
        for cls in reversed(classes):
            bpy.utils.unregister_class(cls)
    for module in reversed(_MODULES_WITH_REGISTER):
        module.unregister()
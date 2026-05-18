import bpy

class DAWProperties(bpy.types.PropertyGroup):
    project_name: bpy.props.StringProperty(
        name="Nome do Projeto",
        default="Novo Projeto"
    )
    sample_rate: bpy.props.IntProperty(
        name="Sample Rate",
        default=44100
    )
    bit_depth: bpy.props.IntProperty(
        name="Bit Depth",
        default=24
    )
    is_playing: bpy.props.BoolProperty(
        name="Executando",
        default=False
    )

# Funções isoladas para o ciclo de registro
def register_properties():
    bpy.utils.register_class(DAWProperties)
    # Vincula o grupo à cena do Blender de forma global
    bpy.types.Scene.daw_props = bpy.props.PointerProperty(type=DAWProperties)

def unregister_properties():
    bpy.utils.unregister_class(DAWProperties)
    del bpy.types.Scene.daw_props
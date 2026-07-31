# modules/project/save.py - ALTERAÇÃO NECESSÁRIA
# ============================================================================
# Este arquivo mostra as LINHAS A ADICIONAR ao save.py existente
# ============================================================================

# ADICIONAR ESTAS LINHAS NO FINAL DA FUNÇÃO serialize_project() 
# (após adicionar mixer, patterns, piano_roll, playlist)

def serialize_project(scene) -> Dict[str, Any]:
    """Serializa o estado completo da DAW em um dicionário."""
    mixer_props = getattr(scene, "daw_mixer", None)
    patterns_props = getattr(scene, "daw_patterns", None)
    pr_props = getattr(scene, "daw_piano_roll", None)
    pl_props = getattr(scene, "daw_playlist", None)

    data = {
        "version": CURRENT_PROJECT_VERSION,
        "project_name": getattr(scene, "daw_project_name", "Untitled"),
        "modules": {},
    }

    if mixer_props is not None:
        data["modules"]["mixer"] = _serialize_mixer(mixer_props)
    if patterns_props is not None:
        data["modules"]["patterns"] = _serialize_patterns(patterns_props)
    if pr_props is not None:
        data["modules"]["piano_roll"] = _serialize_piano_roll(pr_props)
    if pl_props is not None:
        data["modules"]["playlist"] = _serialize_playlist(pl_props)

    # ════════════════════════════════════════════════════════════════
    # NOVO: Serializar VST (adicionar estas linhas)
    # ════════════════════════════════════════════════════════════════
    try:
        from ..vst import persistence as vst_persistence
        vst_data = vst_persistence.serialize_vst_state(scene)
        if vst_data:
            data["modules"]["vst"] = vst_data
    except Exception as e:
        print(f"[DAW] Aviso ao serializar VST: {e}")
    # ════════════════════════════════════════════════════════════════

    return data
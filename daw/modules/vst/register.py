# modules/vst/register.py
"""
Registro e desregistro do módulo VST no Blender.
Chamado por daw/__init__.py no register()/unregister() geral do addon.
"""
from __future__ import annotations

import bpy
from bpy.app.handlers import persistent

from .properties import register as _properties_register, unregister as _properties_unregister
from .operators import classes as _operator_classes
from .ui import classes as _ui_classes
from .utils import get_or_create_live_vst, sync_rna_from_pure


def _reload_all_vsts_in_scene(scene) -> None:
    """
    Recarrega de verdade (via dawdreamer) todo VST que a cena já tinha
    configurado — RNA (`item.vst_path`, `item.is_loaded=True`) sobrevive
    ao salvar/reabrir o .blend, mas o objeto Python/dawdreamer em si NÃO.
    Sem isso, ao reabrir um projeto, os VSTs aparecem "carregados" na UI
    porém não tocam nada até o usuário clicar em Recarregar manualmente
    em cada um — bem longe do que se espera de uma DAW de verdade.
    """
    chains = getattr(scene, "daw_vst_chains", None)
    if chains is not None:
        for chain in chains:
            for item in chain.vsts:
                if not item.vst_path:
                    continue
                vst = get_or_create_live_vst(item)
                vst.load(sample_rate=getattr(getattr(scene, "daw", None), "sample_rate", 44100))
                sync_rna_from_pure(item, vst)

    rack = getattr(scene, "daw_vst_instruments", None)
    if rack is not None:
        for item in rack.instruments:
            if not item.vst_path:
                continue
            vst = get_or_create_live_vst(item)
            vst.load(sample_rate=getattr(getattr(scene, "daw", None), "sample_rate", 44100))
            sync_rna_from_pure(item, vst)


@persistent
def _on_load_post(dummy):
    for scene in bpy.data.scenes:
        try:
            _reload_all_vsts_in_scene(scene)
        except Exception as e:
            print(f"[DAW][vst] Falha ao recarregar VSTs da cena '{scene.name}': {e}")

    _load_scan_cache_into_browser()


def _load_scan_cache_into_browser() -> None:
    """
    Carrega o resultado do último scan salvo (JSON fora do .blend) no VST
    Browser, sem escanear de novo -- é o que faz o painel já vir com a
    lista de plugins preenchida ao abrir o Blender, em vez de exigir
    clicar em "Escanear" toda vez (que agora varre o sistema inteiro e
    pode demorar).
    """
    try:
        from .utils import load_scan_cache, make_unique_vst_id

        found = load_scan_cache()
        if not found:
            return

        for scene in bpy.data.scenes:
            browser = getattr(scene, "daw_vst_browser", None)
            if browser is None or len(browser.discovered_vsts) > 0:
                continue  # já tem algo (ex.: scan manual rodou antes) -- não sobrescreve
            existing_ids = []
            for entry in found:
                item = browser.discovered_vsts.add()
                item.vst_path = entry["path"]
                item.vst_name = entry["name"]
                item.vst_id = make_unique_vst_id(entry["name"], existing_ids)
                existing_ids.append(item.vst_id)
                item.vst_type = "EFFECT"
    except Exception as e:
        print(f"[DAW][vst] Falha ao carregar cache de scan: {e}")


def register():
    # properties.py já cuida do próprio register/unregister (classes +
    # bpy.types.Scene.daw_vst*), então só registramos operators/ui aqui.
    _properties_register()

    for cls in _operator_classes:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
        bpy.utils.register_class(cls)

    for cls in _ui_classes:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
        bpy.utils.register_class(cls)

    if _on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load_post)

    # Recarrega os VSTs do arquivo que já está aberto agora (o load_post
    # só dispara em aberturas futuras de arquivo, não no que já está na tela
    # quando o addon é ativado/atualizado).
    try:
        _on_load_post(None)
    except Exception as e:
        print(f"[DAW][vst] Falha ao recarregar VSTs no registro do addon: {e}")

    print("[DAW] Módulo vst registrado")


def unregister():
    if _on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post)

    # Desliga o processo worker de VST (se estiver rodando) -- sem isso
    # ele fica orfao, vivo, mesmo depois do addon ser desativado/recarregado.
    try:
        from .ipc_engine import shutdown_worker
        shutdown_worker()
    except Exception as e:
        print(f"[DAW][vst] Falha ao desligar worker de VST: {e}")

    for cls in reversed(_ui_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

    for cls in reversed(_operator_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

    _properties_unregister()

    print("[DAW] Módulo vst desregistrado")
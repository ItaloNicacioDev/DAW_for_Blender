# modules/settings/register.py
"""
Registro centralizado de todas as classes e módulos do Settings.

Gerencia a ordem de registro/desregistro garantindo que
dependências sejam resolvidas corretamente.
"""
from __future__ import annotations

import bpy
from . import (
    preferences,
    themes,
    shortcuts,
    utils,
    operators,
    ui,
)


def register():
    """Registra todos os módulos do Settings na ordem correta."""
    
    # 1. Preferências (PropertyGroups necessários antes de UI)
    preferences.register()
    
    # 2. Utilitários (sem dependência em classes Blender)
    themes.register()
    utils.register()
    
    # 3. Operadores (depende de preferências)
    operators.register()
    
    # 4. UI (depende de operadores e preferências)
    ui.register()
    
    # 5. Atalhos (registra keymaps)
    shortcuts.register()


def unregister():
    """Desregistra todos os módulos do Settings em ordem reversa."""
    
    # Ordem reversa: atalhos primeiro
    shortcuts.unregister()
    
    # UI e operadores
    ui.unregister()
    operators.unregister()
    
    # Utilitários
    utils.unregister()
    themes.unregister()
    
    # Preferências por último
    preferences.unregister()


# ============================================================================
# Hook de Inicialização (executado quando o addon é carregado)
# ============================================================================

def on_addon_loaded():
    """Chamado quando o addon DAW é carregado.
    
    Realiza tarefas de inicialização como:
    - Carregar último projeto (se configurado)
    - Verificar atualizações
    - Inicializar diretórios de config
    """
    try:
        prefs = preferences.get_preferences()
        
        # Debug
        if prefs.debug_mode:
            print("[DAW Settings] Addon carregado com sucesso")
            print(f"[DAW Settings] Tema: {prefs.ui.theme}")
            print(f"[DAW Settings] Sample Rate: {prefs.audio.samplerate} Hz")
        
        # Criar diretórios se não existem
        config_dir = utils.get_config_dir()
        if not config_dir.exists():
            config_dir.mkdir(parents=True, exist_ok=True)
            if prefs.debug_mode:
                print(f"[DAW Settings] Diretório de config criado: {config_dir}")
        
        # Verificar atualizações (se habilitado)
        if prefs.check_for_updates:
            check_for_updates_async()
    
    except Exception as e:
        print(f"[DAW Settings] Erro na inicialização: {e}")


def on_addon_unloaded():
    """Chamado quando o addon DAW é descarregado.
    
    Realiza limpeza e salva estado.
    """
    try:
        prefs = preferences.get_preferences()
        
        # Salvar layout atual (se configurado)
        if prefs.workspace.remember_last_project:
            utils.save_workspace_layout()
        
        if prefs.debug_mode:
            print("[DAW Settings] Addon descarregado")
    
    except Exception as e:
        print(f"[DAW Settings] Erro ao descarregar: {e}")


def check_for_updates_async():
    """Verifica atualizações de forma assíncrona.

    Implementado em modules/update (checagem via GitHub Releases,
    throttled e sem travar a UI). Ver modules/update/jobs.py.
    """
    try:
        from ..update import jobs as update_jobs
        update_jobs.maybe_auto_check_on_startup()
    except Exception as e:
        print(f"[DAW Settings] Update indisponível: {e}")


# ============================================================================
# Registro de Handlers (app handlers do Blender)
# ============================================================================

_handlers_registered = False


def register_handlers():
    """Registra handlers do Blender (load_post, etc)."""
    global _handlers_registered
    
    if _handlers_registered:
        return
    
    try:
        # Handler executado após carregar arquivo .blend
        bpy.app.handlers.load_post.append(on_blend_file_loaded)
        bpy.app.handlers.save_post.append(on_blend_file_saved)
        
        _handlers_registered = True
    except Exception as e:
        print(f"[DAW Settings] Erro ao registrar handlers: {e}")


def unregister_handlers():
    """Desregistra handlers do Blender."""
    global _handlers_registered
    
    if not _handlers_registered:
        return
    
    try:
        bpy.app.handlers.load_post.remove(on_blend_file_loaded)
        bpy.app.handlers.save_post.remove(on_blend_file_saved)
        
        _handlers_registered = False
    except Exception as e:
        print(f"[DAW Settings] Erro ao desregistrar handlers: {e}")


def on_blend_file_loaded(dummy):
    """Handler executado quando um arquivo .blend é carregado."""
    try:
        prefs = preferences.get_preferences()
        
        if prefs.debug_mode:
            print("[DAW Settings] Arquivo .blend carregado")
    except Exception:
        pass


def on_blend_file_saved(dummy):
    """Handler executado quando um arquivo .blend é salvo."""
    try:
        prefs = preferences.get_preferences()
        
        if prefs.debug_mode:
            print("[DAW Settings] Arquivo .blend salvo")
        
        # Auto-save (se habilitado)
        if prefs.workspace.autosave_interval > 0:
            # TODO: Implementar auto-save timer
            pass
    except Exception:
        pass
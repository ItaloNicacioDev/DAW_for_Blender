# modules/updater/ui.py
"""
Desenho da seção de atualizações — usado tanto no painel principal de
Preferences (compacto) quanto no painel dedicado "Atualizações" dentro
das abas da DAW em Preferences (completo, com changelog).
"""
from __future__ import annotations

from . import jobs
from .properties import get_updater_state


def draw_updater_compact(layout, context):
    """Versão compacta: uma linha de status + botão de ação. Pensada
    para ficar logo abaixo de 'Verificar Atualizações' no painel
    principal de Preferences (Add-ons)."""
    st = get_updater_state(context)
    row = layout.row(align=True)

    if st.status == 'CHECKING':
        row.label(text="Verificando atualizações...", icon='SORTTIME')
    elif st.status == 'UPDATE_AVAILABLE':
        row.label(text=f"Nova versão disponível: {st.latest_version}", icon='INFO')
        row.operator("daw.updater_download_install", text="Atualizar", icon='IMPORT')
    elif st.status == 'DOWNLOADING':
        row.label(text=f"Baixando atualização... {int(st.progress * 100)}%", icon='SORTTIME')
    elif st.status == 'INSTALLING':
        row.label(text="Instalando atualização...", icon='SORTTIME')
    elif st.status == 'DONE_INSTALL':
        row.label(text="Atualização instalada — reinicie o Blender", icon='ERROR')
        row.operator("daw.updater_restart_blender", text="Reiniciar", icon='FILE_REFRESH')
    elif st.status == 'ERROR':
        row.label(text=f"Erro ao atualizar: {st.error}", icon='ERROR')
        row.operator("daw.updater_check", text="Tentar Novamente", icon='FILE_REFRESH')
    else:
        row.operator("daw.updater_check", text="Verificar Atualizações", icon='FILE_REFRESH')
        row.label(text=f"v{jobs.get_local_version_str()} instalada")


def draw_updater_full(layout, context):
    """Versão completa, com changelog e todos os estados — pensada
    para o painel dedicado 'Atualizações'."""
    st = get_updater_state(context)

    box = layout.box()
    row = box.row()
    row.label(text="Verificação de Atualizações", icon='FILE_REFRESH')

    col = box.column(align=True)
    col.label(text=f"Versão instalada: v{jobs.get_local_version_str()}")

    box.separator()

    if st.status == 'IDLE':
        box.operator("daw.updater_check", icon='URL', text="Verificar Atualizações")

    elif st.status == 'CHECKING':
        box.label(text="Verificando no GitHub...", icon='SORTTIME')

    elif st.status == 'UP_TO_DATE':
        box.label(text="Você já está na versão mais recente.", icon='CHECKMARK')
        box.operator("daw.updater_check", text="Verificar Novamente", icon='FILE_REFRESH')

    elif st.status == 'UPDATE_AVAILABLE':
        box.label(text=f"Nova versão disponível: {st.latest_version}", icon='INFO')
        if st.changelog:
            box.label(text="Notas da versão:")
            col = box.column(align=True)
            for line in st.changelog.splitlines():
                line = line.strip()
                if not line:
                    continue
                col.label(text=line[:90])
        box.operator("daw.updater_download_install", icon='IMPORT', text="Baixar e Instalar Agora")

    elif st.status == 'DOWNLOADING':
        box.label(text=f"Baixando... {int(st.progress * 100)}%", icon='SORTTIME')
        box.prop(st, "progress", text="Progresso", slider=True)

    elif st.status == 'INSTALLING':
        box.label(text="Instalando arquivos...", icon='SORTTIME')

    elif st.status == 'DONE_INSTALL':
        box.label(text="Atualização instalada com sucesso!", icon='CHECKMARK')
        box.label(text="Salve seu trabalho e reinicie o Blender para concluir.", icon='ERROR')
        box.operator("daw.updater_restart_blender", icon='FILE_REFRESH', text="Salvar e Reiniciar o Blender")

    elif st.status == 'ERROR':
        box.label(text="Ocorreu um erro:", icon='ERROR')
        col = box.column(align=True)
        col.label(text=st.error[:200] if st.error else "Erro desconhecido")
        box.operator("daw.updater_check", text="Tentar Novamente", icon='FILE_REFRESH')

    box.separator()
    box.operator("daw.updater_open_releases", text="Ver Releases no GitHub", icon='URL')
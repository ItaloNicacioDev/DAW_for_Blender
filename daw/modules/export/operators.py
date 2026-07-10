# modules/export/operators.py
"""
Operators do Blender para o módulo de Exportação.

Responsabilidade:
    Disparar a exportação do projeto (notas do Piano Roll) no formato
    escolhido em context.scene.daw_export, delegando a renderização/
    transcodificação para wav.py, midi.py, mp3.py, ogg.py e flac.py.
"""
from __future__ import annotations

from pathlib import Path

import bpy
from bpy.types import Operator

from .wav import export_notes_to_wav
from .midi import export_notes_to_midi
from .mp3 import export_wav_to_mp3
from .ogg import export_wav_to_ogg
from .flac import export_wav_to_flac
from .utils import (
    get_notes_from_scene,
    ensure_extension,
    make_temp_wav_path,
    cleanup_temp_file,
)


def _export_base_path(context) -> Path:
    props = context.scene.daw_export
    export_dir = Path(bpy.path.abspath(props.export_path or "//"))
    export_dir.mkdir(parents=True, exist_ok=True)
    filename = props.filename.strip() or "export"
    return export_dir / filename


class DAW_OT_ExportProject(Operator):
    bl_idname = "daw.export_project"
    bl_label = "Exportar"
    bl_description = "Exporta o projeto (notas do Piano Roll) no formato configurado"
    bl_options = {'REGISTER'}

    def execute(self, context):
        props = context.scene.daw_export
        notes, bpm = get_notes_from_scene(context)

        if not notes and props.format != "MIDI":
            self.report({'WARNING'}, "Nenhuma nota encontrada no Piano Roll — exportando silêncio")

        base_path = _export_base_path(context)
        sample_rate = int(props.sample_rate)

        try:
            if props.format == "MIDI":
                final_path = export_notes_to_midi(
                    notes, bpm,
                    ensure_extension(base_path, "mid"),
                    ppq=props.midi_ppq,
                )
                ok, message = True, f"MIDI exportado: {final_path}"

            elif props.format == "WAV":
                final_path = export_notes_to_wav(
                    notes, bpm,
                    ensure_extension(base_path, "wav"),
                    sample_rate=sample_rate,
                    wave_shape=props.wave_shape,
                    normalize=props.normalize,
                )
                ok, message = True, f"WAV exportado: {final_path}"

            else:
                # MP3 / OGG / FLAC: renderiza um WAV temporário e transcodifica via ffmpeg
                temp_wav = make_temp_wav_path()
                try:
                    export_notes_to_wav(
                        notes, bpm, temp_wav,
                        sample_rate=sample_rate,
                        wave_shape=props.wave_shape,
                        normalize=props.normalize,
                    )

                    if props.format == "MP3":
                        ok, message = export_wav_to_mp3(
                            temp_wav, ensure_extension(base_path, "mp3"),
                            bitrate_kbps=int(props.mp3_bitrate),
                        )
                    elif props.format == "OGG":
                        ok, message = export_wav_to_ogg(
                            temp_wav, ensure_extension(base_path, "ogg"),
                            quality=props.ogg_quality,
                        )
                    elif props.format == "FLAC":
                        ok, message = export_wav_to_flac(
                            temp_wav, ensure_extension(base_path, "flac"),
                            compression_level=props.flac_compression,
                        )
                    else:
                        ok, message = False, f"Formato desconhecido: {props.format}"
                finally:
                    cleanup_temp_file(temp_wav)

        except Exception as ex:
            ok, message = False, f"Erro inesperado durante a exportação: {ex}"

        props.last_export_status = message
        props.last_export_ok = ok

        if ok:
            self.report({'INFO'}, message)
            return {'FINISHED'}

        self.report({'ERROR'}, message)
        return {'CANCELLED'}


class DAW_OT_OpenExportFolder(Operator):
    bl_idname = "daw.open_export_folder"
    bl_label = "Abrir Pasta"
    bl_description = "Abre a pasta de destino da exportação no explorador de arquivos do sistema"
    bl_options = {'REGISTER'}

    def execute(self, context):
        props = context.scene.daw_export
        folder = Path(bpy.path.abspath(props.export_path or "//"))
        folder.mkdir(parents=True, exist_ok=True)

        try:
            bpy.ops.wm.path_open(filepath=str(folder))
        except Exception as ex:
            self.report({'ERROR'}, f"Não foi possível abrir a pasta: {ex}")
            return {'CANCELLED'}

        return {'FINISHED'}


classes = [
    DAW_OT_ExportProject,
    DAW_OT_OpenExportFolder,
]
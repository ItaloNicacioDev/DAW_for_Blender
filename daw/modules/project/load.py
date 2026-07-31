# modules/project/load.py
"""
Carregamento de projetos da DAW.

Responsabilidade:
    Ler um arquivo JSON de projeto e restaurar o estado completo
    da DAW nos PropertyGroups RNA da cena.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import bpy

from .utils import is_valid_project_file


def _deserialize_mixer(mixer_props, data: Dict[str, Any]) -> None:
    """Restaura o estado do mixer a partir do dict."""
    mixer_props.master_volume = data.get("master_volume", 0.85)
    mixer_props.meters_enabled = data.get("meters_enabled", True)
    mixer_props.meter_decay_speed = data.get("meter_decay_speed", 8.0)

    mixer_props.tracks.clear()
    for t_data in data.get("tracks", []):
        t = mixer_props.tracks.add()
        t.name = t_data.get("name", "Track")
        t.color = tuple(t_data.get("color", [0.6, 0.6, 0.6]))
        t.volume = t_data.get("volume", 0.78)
        t.pan = t_data.get("pan", 0.0)
        t.mute = t_data.get("mute", False)
        t.solo = t_data.get("solo", False)
        t.output_bus = t_data.get("output_bus", "Master")
        t.source_index = t_data.get("source_index", -1)

        for ins_data in t_data.get("inserts", []):
            ins = t.inserts.add()
            ins.effect_type = ins_data.get("effect_type", "EQ")
            ins.enabled = ins_data.get("enabled", True)
            ins.bypass = ins_data.get("bypass", False)
            for key, value in ins_data.get("params", {}).items():
                p = ins.params.add()
                p.name = key
                p.value = float(value)

        for s_data in t_data.get("sends", []):
            s = t.sends.add()
            s.bus_name = s_data.get("bus_name", "")
            s.level = s_data.get("level", 0.0)
            s.pre_fader = s_data.get("pre_fader", False)
            s.enabled = s_data.get("enabled", True)

    mixer_props.buses.clear()
    for b_data in data.get("buses", []):
        b = mixer_props.buses.add()
        b.name = b_data.get("name", "Bus")
        b.volume = b_data.get("volume", 0.8)
        b.mute = b_data.get("mute", False)
        b.is_master = b_data.get("is_master", False)

    # Garante que o Master exista
    if len(mixer_props.buses) == 0 or not mixer_props.buses[0].is_master:
        master = mixer_props.buses.add()
        master.name = "Master"
        master.volume = 0.8
        master.is_master = True
        if len(mixer_props.buses) > 1:
            mixer_props.buses.move(len(mixer_props.buses) - 1, 0)


def _deserialize_patterns(patterns_props, data: Dict[str, Any]) -> None:
    """Restaura o estado dos patterns."""
    patterns_props.patterns.clear()
    for p_data in data.get("patterns", []):
        p = patterns_props.patterns.add()
        p.name = p_data.get("name", "Pattern")
        p.color = tuple(p_data.get("color", [0.6, 0.6, 0.6]))
        p.length_steps = p_data.get("length_steps", 16)
        p.bpm = p_data.get("bpm", 120.0)
        p.time_signature_num = p_data.get("time_signature_num", 4)
        p.time_signature_den = p_data.get("time_signature_den", 4)
        p.is_looping = p_data.get("is_looping", True)
        p.swing = p_data.get("swing", 0.0)

        for n_data in p_data.get("notes", []):
            n = p.notes.add()
            n.pitch = n_data.get("pitch", 60)
            n.velocity = n_data.get("velocity", 0.8)
            n.start_step = n_data.get("start_step", 0)
            n.duration_steps = n_data.get("duration_steps", 1)
            n.enabled = n_data.get("enabled", True)

    patterns_props.clips.clear()
    for c_data in data.get("clips", []):
        c = patterns_props.clips.add()
        c.pattern_name = c_data.get("pattern_name", "")
        c.track_index = c_data.get("track_index", 0)
        c.start_beat = c_data.get("start_beat", 0.0)
        c.duration_beats = c_data.get("duration_beats", 4.0)
        c.offset_beats = c_data.get("offset_beats", 0.0)
        c.enabled = c_data.get("enabled", True)
        c.use_color_override = c_data.get("use_color_override", False)
        if c.use_color_override and c_data.get("color_override"):
            c.color_override = tuple(c_data["color_override"])

    patterns_props.groups.clear()
    for g_data in data.get("groups", []):
        g = patterns_props.groups.add()
        g.name = g_data.get("name", "Grupo")
        g.color = tuple(g_data.get("color", [0.6, 0.6, 0.6]))
        g.pattern_names_csv = g_data.get("pattern_names_csv", "")


def _deserialize_piano_roll(pr_props, data: Dict[str, Any]) -> None:
    """Restaura o estado do piano roll."""
    pr_props.edited_pattern_name = data.get("edited_pattern_name", "")

    pr_props.notes.clear()
    for n_data in data.get("notes", []):
        n = pr_props.notes.add()
        n.pitch = n_data.get("pitch", 60)
        n.start_beat = n_data.get("start_beat", 0.0)
        n.duration_beats = n_data.get("duration_beats", 0.25)
        n.velocity = n_data.get("velocity", 0.8)
        n.selected = n_data.get("selected", False)
        n.muted = n_data.get("muted", False)

    settings = data.get("settings", {})
    pr_props.settings.snap_enabled = settings.get("snap_enabled", True)
    pr_props.settings.snap_division = settings.get("snap_division", "SIXTEENTH")
    pr_props.settings.scale_enabled = settings.get("scale_enabled", False)
    pr_props.settings.scale_root = settings.get("scale_root", 60)
    pr_props.settings.scale_name = settings.get("scale_name", "MAJOR")
    pr_props.settings.zoom_x = settings.get("zoom_x", 1.0)
    pr_props.settings.zoom_y = settings.get("zoom_y", 1.0)


def _deserialize_playlist(pl_props, data: Dict[str, Any]) -> None:
    """Restaura o estado da playlist."""
    pl_props.tracks.clear()
    for t_data in data.get("tracks", []):
        t = pl_props.tracks.add()
        t.name = t_data.get("name", "Track")
        t.mixer_track_index = t_data.get("mixer_track_index", 0)
        t.color = tuple(t_data.get("color", [0.6, 0.6, 0.6]))
        t.muted = t_data.get("muted", False)
        t.solo = t_data.get("solo", False)
        t.locked = t_data.get("locked", False)
        t.height = t_data.get("height", 40)

    pl_props.clips.clear()
    for c_data in data.get("clips", []):
        c = pl_props.clips.add()
        c.name = c_data.get("name", "Clip")
        c.clip_type = c_data.get("clip_type", "PATTERN")
        c.track_index = c_data.get("track_index", 0)
        c.start_beat = c_data.get("start_beat", 0.0)
        c.duration_beats = c_data.get("duration_beats", 4.0)
        c.pattern_name = c_data.get("pattern_name", "")
        c.audio_path = c_data.get("audio_path", "")
        c.automation_param = c_data.get("automation_param", "")
        c.content_offset_beats = c_data.get("content_offset_beats", 0.0)
        c.muted = c_data.get("muted", False)
        c.locked = c_data.get("locked", False)
        c.use_color_override = c_data.get("use_color_override", False)
        if c.use_color_override and c_data.get("color_override"):
            c.color_override = tuple(c_data["color_override"])

    pl_props.markers.clear()
    for m_data in data.get("markers", []):
        m = pl_props.markers.add()
        m.name = m_data.get("name", "Marcador")
        m.beat = m_data.get("beat", 0.0)
        m.color = tuple(m_data.get("color", [0.9, 0.3, 0.3]))

    pb = data.get("playback", {})
    pl_props.playback.current_bpm = pb.get("current_bpm", 120.0)
    pl_props.playback.time_signature_num = pb.get("time_signature_num", 4)
    pl_props.playback.time_signature_den = pb.get("time_signature_den", 4)
    pl_props.playback.loop_enabled = pb.get("loop_enabled", False)
    pl_props.playback.loop_start_beat = pb.get("loop_start_beat", 0.0)
    pl_props.playback.loop_end_beat = pb.get("loop_end_beat", 16.0)
    pl_props.playback.metronome_enabled = pb.get("metronome_enabled", False)


def deserialize_project(scene, data: Dict[str, Any]) -> bool:
    """Restaura o estado completo da DAW a partir de um dicionário."""
    modules = data.get("modules", {})

    mixer_props = getattr(scene, "daw_mixer", None)
    if mixer_props is not None and "mixer" in modules:
        _deserialize_mixer(mixer_props, modules["mixer"])

    patterns_props = getattr(scene, "daw_patterns", None)
    if patterns_props is not None and "patterns" in modules:
        _deserialize_patterns(patterns_props, modules["patterns"])

    pr_props = getattr(scene, "daw_piano_roll", None)
    if pr_props is not None and "piano_roll" in modules:
        _deserialize_piano_roll(pr_props, modules["piano_roll"])

    pl_props = getattr(scene, "daw_playlist", None)
    if pl_props is not None and "playlist" in modules:
        _deserialize_playlist(pl_props, modules["playlist"])

    # Metadados
    if "project_name" in data:
        scene.daw_project_name = data["project_name"]

    return True


def load_project(filepath: str, context: bpy.context) -> bool:
    """Carrega um projeto da DAW."""
    scene = context.scene
    
    if not is_valid_project_file(filepath):
        return False
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False
    
    modules = data.get("modules", {})
    
    # Restaurar cada módulo (código existente)
    if "mixer" in modules:
        mixer_props = getattr(scene, "daw_mixer", None)
        if mixer_props is not None:
            _deserialize_mixer(mixer_props, modules["mixer"])
    
    if "patterns" in modules:
        patterns_props = getattr(scene, "daw_patterns", None)
        if patterns_props is not None:
            _deserialize_patterns(patterns_props, modules["patterns"])
    
    if "piano_roll" in modules:
        pr_props = getattr(scene, "daw_piano_roll", None)
        if pr_props is not None:
            _deserialize_piano_roll(pr_props, modules["piano_roll"])
    
    if "playlist" in modules:
        pl_props = getattr(scene, "daw_playlist", None)
        if pl_props is not None:
            _deserialize_playlist(pl_props, modules["playlist"])
    
    # ════════════════════════════════════════════════════════════════
    # NOVO: Restaurar VST (adicionar estas linhas)
    # ════════════════════════════════════════════════════════════════
    if "vst" in modules:
        try:
            from ..vst import persistence as vst_persistence
            vst_persistence.restore_vst_state(scene, modules["vst"], context)
        except Exception as e:
            print(f"[DAW] Aviso ao restaurar VST: {e}")
    # ════════════════════════════════════════════════════════════════
    
    return True
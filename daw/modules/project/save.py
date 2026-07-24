# modules/project/save.py
"""
Salvamento de projetos da DAW.

Responsabilidade:
    Serializar o estado completo da DAW (mixer, patterns, piano_roll,
    playlist) em um dicionário JSON-safe e gravar em disco.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import bpy

from .utils import ensure_extension

CURRENT_PROJECT_VERSION = "1.0"


def _serialize_mixer(mixer_props) -> Dict[str, Any]:
    """Serializa o estado do mixer."""
    return {
        "master_volume": mixer_props.master_volume,
        "meters_enabled": mixer_props.meters_enabled,
        "meter_decay_speed": mixer_props.meter_decay_speed,
        "tracks": [
            {
                "name": t.name,
                "color": list(t.color),
                "volume": t.volume,
                "pan": t.pan,
                "mute": t.mute,
                "solo": t.solo,
                "output_bus": t.output_bus,
                "source_index": t.source_index,
                "inserts": [
                    {
                        "effect_type": ins.effect_type,
                        "enabled": ins.enabled,
                        "bypass": ins.bypass,
                        "params": {p.name: p.value for p in ins.params},
                    }
                    for ins in t.inserts
                ],
                "sends": [
                    {
                        "bus_name": s.bus_name,
                        "level": s.level,
                        "pre_fader": s.pre_fader,
                        "enabled": s.enabled,
                    }
                    for s in t.sends
                ],
            }
            for t in mixer_props.tracks
        ],
        "buses": [
            {
                "name": b.name,
                "volume": b.volume,
                "mute": b.mute,
                "is_master": b.is_master,
            }
            for b in mixer_props.buses
        ],
    }


def _serialize_patterns(patterns_props) -> Dict[str, Any]:
    """Serializa o estado dos patterns."""
    return {
        "patterns": [
            {
                "name": p.name,
                "color": list(p.color),
                "length_steps": p.length_steps,
                "bpm": p.bpm,
                "time_signature_num": p.time_signature_num,
                "time_signature_den": p.time_signature_den,
                "is_looping": p.is_looping,
                "swing": p.swing,
                "notes": [
                    {
                        "pitch": n.pitch,
                        "velocity": n.velocity,
                        "start_step": n.start_step,
                        "duration_steps": n.duration_steps,
                        "enabled": n.enabled,
                    }
                    for n in p.notes
                ],
            }
            for p in patterns_props.patterns
        ],
        "clips": [
            {
                "pattern_name": c.pattern_name,
                "track_index": c.track_index,
                "start_beat": c.start_beat,
                "duration_beats": c.duration_beats,
                "offset_beats": c.offset_beats,
                "enabled": c.enabled,
                "use_color_override": c.use_color_override,
                "color_override": list(c.color_override) if c.use_color_override else None,
            }
            for c in patterns_props.clips
        ],
        "groups": [
            {
                "name": g.name,
                "color": list(g.color),
                "pattern_names_csv": g.pattern_names_csv,
            }
            for g in patterns_props.groups
        ],
    }


def _serialize_piano_roll(pr_props) -> Dict[str, Any]:
    """Serializa o estado do piano roll."""
    return {
        "edited_pattern_name": pr_props.edited_pattern_name,
        "notes": [
            {
                "pitch": n.pitch,
                "start_beat": n.start_beat,
                "duration_beats": n.duration_beats,
                "velocity": n.velocity,
                "selected": n.selected,
                "muted": n.muted,
            }
            for n in pr_props.notes
        ],
        "settings": {
            "snap_enabled": pr_props.settings.snap_enabled,
            "snap_division": pr_props.settings.snap_division,
            "scale_enabled": pr_props.settings.scale_enabled,
            "scale_root": pr_props.settings.scale_root,
            "scale_name": pr_props.settings.scale_name,
            "zoom_x": pr_props.settings.zoom_x,
            "zoom_y": pr_props.settings.zoom_y,
        },
    }


def _serialize_playlist(pl_props) -> Dict[str, Any]:
    """Serializa o estado da playlist."""
    return {
        "tracks": [
            {
                "name": t.name,
                "mixer_track_index": t.mixer_track_index,
                "color": list(t.color),
                "muted": t.muted,
                "solo": t.solo,
                "locked": t.locked,
                "height": t.height,
            }
            for t in pl_props.tracks
        ],
        "clips": [
            {
                "name": c.name,
                "clip_type": c.clip_type,
                "track_index": c.track_index,
                "start_beat": c.start_beat,
                "duration_beats": c.duration_beats,
                "pattern_name": c.pattern_name,
                "audio_path": c.audio_path,
                "automation_param": c.automation_param,
                "content_offset_beats": c.content_offset_beats,
                "muted": c.muted,
                "locked": c.locked,
                "use_color_override": c.use_color_override,
                "color_override": list(c.color_override) if c.use_color_override else None,
            }
            for c in pl_props.clips
        ],
        "markers": [
            {
                "name": m.name,
                "beat": m.beat,
                "color": list(m.color),
            }
            for m in pl_props.markers
        ],
        "playback": {
            "current_bpm": pl_props.playback.current_bpm,
            "time_signature_num": pl_props.playback.time_signature_num,
            "time_signature_den": pl_props.playback.time_signature_den,
            "loop_enabled": pl_props.playback.loop_enabled,
            "loop_start_beat": pl_props.playback.loop_start_beat,
            "loop_end_beat": pl_props.playback.loop_end_beat,
            "metronome_enabled": pl_props.playback.metronome_enabled,
        },
    }


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

    return data


def save_project(filepath: str, scene) -> bool:
    """Salva o projeto em um arquivo JSON."""
    filepath = ensure_extension(filepath)
    data = serialize_project(scene)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except (OSError, TypeError):
        return False
#ifndef DAW_ENGINE_H
#define DAW_ENGINE_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>
#include <stdbool.h>

/* ────────────────────────────────────────────────────────────
   VERSÃO & LIMITES
──────────────────────────────────────────────────────────── */
#define DAW_VERSION_STR         "0.2.0"
#define DAW_MAX_TRACKS          64
#define DAW_MAX_CLIPS_PER_TRACK 128
#define DAW_CHANNELS            2
#define DAW_DEFAULT_SR          44100
#define DAW_DEFAULT_BPM         120.0
#define DAW_DEFAULT_BUFFER      512

/* ────────────────────────────────────────────────────────────
   CÓDIGOS DE RETORNO
──────────────────────────────────────────────────────────── */
typedef int32_t daw_result_t;

#define DAW_OK               ((daw_result_t)  0)
#define DAW_ERR_NOT_INIT     ((daw_result_t) -1)
#define DAW_ERR_ALREADY_INIT ((daw_result_t) -2)
#define DAW_ERR_AUDIO_DEVICE ((daw_result_t) -3)
#define DAW_ERR_INVALID_TRACK ((daw_result_t)-4)
#define DAW_ERR_FILE_NOT_FOUND ((daw_result_t)-5)
#define DAW_ERR_OUT_OF_MEMORY ((daw_result_t)-6)
#define DAW_ERR_INVALID_PARAM ((daw_result_t)-7)
#define DAW_ERR_CLIP_FULL    ((daw_result_t) -8)

/* ────────────────────────────────────────────────────────────
   ENUMS
──────────────────────────────────────────────────────────── */
typedef enum { DAW_STATE_STOPPED=0, DAW_STATE_PLAYING=1,
               DAW_STATE_RECORDING=2, DAW_STATE_PAUSED=3 } daw_transport_state_t;

typedef enum { DAW_TRACK_AUDIO=0, DAW_TRACK_MIDI=1,
               DAW_TRACK_BUS=2, DAW_TRACK_MASTER=3 } daw_track_type_t;

/* ────────────────────────────────────────────────────────────
   STRUCTS  (espelhadas exatamente em Python ctypes)
──────────────────────────────────────────────────────────── */
typedef struct {
    uint32_t sample_rate;
    uint32_t bit_depth;
    uint32_t buffer_frames;
    double   bpm;
} daw_config_t;

typedef struct {
    daw_transport_state_t transport;
    double   bpm;
    uint32_t sample_rate;
    uint32_t bit_depth;
    double   position_beats;
    double   position_seconds;
    uint32_t bar;
    uint32_t beat;
    float    master_volume;
    float    master_peak_l;
    float    master_peak_r;
    uint32_t track_count;
    bool     loop_enabled;
    double   loop_start_beat;
    double   loop_end_beat;
} daw_state_t;

typedef struct {
    uint32_t         id;
    daw_track_type_t type;
    char             name[64];
    float            volume;
    float            pan;
    bool             muted;
    bool             soloed;
    bool             armed;
    float            peak_l;
    float            peak_r;
    uint32_t         clip_count;
} daw_track_info_t;

/* ────────────────────────────────────────────────────────────
   API
──────────────────────────────────────────────────────────── */
/* Lifecycle */
daw_result_t daw_init      (const daw_config_t *cfg);
daw_result_t daw_shutdown  (void);
daw_result_t daw_get_state (daw_state_t *out);
const char*  daw_version   (void);
const char*  daw_strerror  (daw_result_t err);

/* Transport */
daw_result_t daw_play    (void);
daw_result_t daw_stop    (void);
daw_result_t daw_pause   (void);
daw_result_t daw_record  (void);
daw_result_t daw_seek    (double beat);
daw_result_t daw_set_bpm (double bpm);
daw_result_t daw_set_loop(bool enabled, double start_beat, double end_beat);

/* Master */
daw_result_t daw_set_master_volume(float volume);
daw_result_t daw_get_master_peaks (float *out_l, float *out_r);

/* Tracks */
daw_result_t daw_track_create   (daw_track_type_t type, uint32_t *out_id);
daw_result_t daw_track_destroy  (uint32_t id);
daw_result_t daw_track_info     (uint32_t id, daw_track_info_t *out);
daw_result_t daw_track_set_name (uint32_t id, const char *name);
daw_result_t daw_track_set_vol  (uint32_t id, float volume);
daw_result_t daw_track_set_pan  (uint32_t id, float pan);
daw_result_t daw_track_set_mute (uint32_t id, bool muted);
daw_result_t daw_track_set_solo (uint32_t id, bool soloed);
daw_result_t daw_track_set_armed(uint32_t id, bool armed);
daw_result_t daw_track_load_file(uint32_t id, const char *path);

#ifdef __cplusplus
}
#endif
#endif /* DAW_ENGINE_H */

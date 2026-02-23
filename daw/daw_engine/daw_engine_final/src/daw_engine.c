/*
 * daw_engine.c  —  Motor de áudio principal
 *
 * COMPILAR (substitua miniaudio.h pelo real antes):
 *   Linux : gcc -O2 -shared -fPIC -o ../bin/daw_engine.so daw_engine.c -lpthread -lm -ldl
 *   macOS : gcc -O2 -dynamiclib  -o ../bin/daw_engine.dylib daw_engine.c -lpthread -lm
 *   Win   : gcc -O2 -shared      -o ../bin/daw_engine.dll   daw_engine.c -lwinmm -lole32
 *
 * Com o Makefile incluso: make  (ou make debug)
 */

#define MINIAUDIO_IMPLEMENTATION
#include "miniaudio.h"
#include "daw_engine.h"

#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <math.h>
#include <pthread.h>

/* ════════════════════════════════════════════════════════════
   ESTRUTURAS INTERNAS
═══════════════════════════════════════════════════════════════ */

typedef struct {
    float   *l, *r;          /* samples deinterleaved */
    uint64_t n;              /* número de frames      */
    double   start_beat;
    double   len_beats;
    bool     active;
} clip_t;

typedef struct {
    bool             active;
    uint32_t         id;
    daw_track_type_t type;
    char             name[64];
    float            vol;
    float            pan;
    bool             muted, soloed, armed;
    float            peak_l, peak_r;
    clip_t           clips[DAW_MAX_CLIPS_PER_TRACK];
    uint32_t         n_clips;
} track_t;

typedef struct {
    bool                  ready;
    ma_device             device;

    /* Transport */
    daw_transport_state_t state;
    double                bpm;
    double                pos_beats;
    double                pos_secs;
    bool                  loop_on;
    double                loop_start, loop_end;

    /* Config */
    uint32_t sr, bits, buf_frames;

    /* Tracks */
    track_t  tracks[DAW_MAX_TRACKS];
    uint32_t n_tracks;
    bool     any_solo;

    /* Master */
    float    master_vol;
    float    master_peak_l, master_peak_r;

    pthread_mutex_t lock;
} ctx_t;

static ctx_t G = {0};

/* ════════════════════════════════════════════════════════════
   HELPERS
═══════════════════════════════════════════════════════════════ */

static inline float clampf(float v, float lo, float hi) {
    return v < lo ? lo : v > hi ? hi : v;
}

/* Pan law de potência constante: ganho L/R a partir de pan [-1,+1] */
static void pan_gains(float pan, float *gl, float *gr) {
    float a = (pan + 1.0f) * (float)(M_PI / 4.0);
    *gl = cosf(a);
    *gr = sinf(a);
}

/* Atualiza medidor de pico com decaimento exponencial suave */
static inline void peak_update(float *p, float s) {
    float a = fabsf(s);
    if (a > *p) *p = a; else *p *= 0.9997f;
}

static track_t *find_track(uint32_t id) {
    for (int i = 0; i < DAW_MAX_TRACKS; i++)
        if (G.tracks[i].active && G.tracks[i].id == id)
            return &G.tracks[i];
    return NULL;
}

static void refresh_solo(void) {
    G.any_solo = false;
    for (int i = 0; i < DAW_MAX_TRACKS; i++)
        if (G.tracks[i].active && G.tracks[i].soloed)
            { G.any_solo = true; break; }
}

/* ════════════════════════════════════════════════════════════
   CALLBACK DE ÁUDIO  (roda na thread de áudio do miniaudio)
═══════════════════════════════════════════════════════════════ */

static void audio_cb(ma_device *dev, void *out, const void *in, ma_uint32 nf) {
    (void)dev;
    (void)dev; (void)in;
    float *dst = (float *)out;

    /* Silencia sempre que não estiver tocando */
    if (!G.ready || (G.state != DAW_STATE_PLAYING && G.state != DAW_STATE_RECORDING)) {
        memset(dst, 0, sizeof(float) * nf * DAW_CHANNELS);
        return;
    }

    /* Buffers de mix da mixagem temporária */
    float mix_l[DAW_DEFAULT_BUFFER], mix_r[DAW_DEFAULT_BUFFER];
    memset(mix_l, 0, sizeof(float) * nf);
    memset(mix_r, 0, sizeof(float) * nf);

    pthread_mutex_lock(&G.lock);

    double spb = 60.0 / G.bpm;                /* segundos por beat     */
    double spf = 1.0  / (double)G.sr;          /* segundos por frame    */
    double bpf = spf  / spb;                   /* beats por frame       */

    /* ── Mix de cada track ── */
    for (int ti = 0; ti < DAW_MAX_TRACKS; ti++) {
        track_t *t = &G.tracks[ti];
        if (!t->active || t->muted) continue;
        if (G.any_solo && !t->soloed) continue;

        float gl, gr;
        pan_gains(t->pan, &gl, &gr);
        gl *= t->vol;
        gr *= t->vol;

        float tpl = 0, tpr = 0;

        for (uint32_t ci = 0; ci < t->n_clips; ci++) {
            clip_t *cl = &t->clips[ci];
            if (!cl->active) continue;

            double cl_end = cl->start_beat + cl->len_beats;

            for (uint32_t f = 0; f < nf; f++) {
                double beat_at = G.pos_beats + f * bpf;

                /* Loop do engine */
                if (G.loop_on && beat_at >= G.loop_end)
                    beat_at = G.loop_start + fmod(beat_at - G.loop_start,
                                                   G.loop_end - G.loop_start);

                if (beat_at < cl->start_beat || beat_at >= cl_end) continue;

                double offset = (beat_at - cl->start_beat) / cl->len_beats;
                uint64_t fi   = (uint64_t)(offset * (double)cl->n);
                if (fi >= cl->n) continue;

                float sl = cl->l[fi] * gl;
                float sr = cl->r[fi] * gr;
                mix_l[f] += sl;
                mix_r[f] += sr;
                peak_update(&tpl, sl);
                peak_update(&tpr, sr);
            }
        }

        t->peak_l = tpl;
        t->peak_r = tpr;
    }

    /* ── Aplica volume master → interleave L/R → output ── */
    float mv = G.master_vol;
    for (uint32_t f = 0; f < nf; f++) {
        float l = clampf(mix_l[f] * mv, -1.0f, 1.0f);
        float r = clampf(mix_r[f] * mv, -1.0f, 1.0f);
        dst[f * 2 + 0] = l;
        dst[f * 2 + 1] = r;
        peak_update(&G.master_peak_l, l);
        peak_update(&G.master_peak_r, r);
    }

    /* Avança playhead */
    double delta_secs  = (double)nf * spf;
    G.pos_secs  += delta_secs;
    G.pos_beats += delta_secs / spb;

    if (G.loop_on && G.pos_beats >= G.loop_end) {
        G.pos_beats = G.loop_start;
        G.pos_secs  = G.loop_start * spb;
    }

    pthread_mutex_unlock(&G.lock);
}

/* ════════════════════════════════════════════════════════════
   LIFECYCLE
═══════════════════════════════════════════════════════════════ */

daw_result_t daw_init(const daw_config_t *cfg) {
    if (G.ready) return DAW_ERR_ALREADY_INIT;

    memset(&G, 0, sizeof(G));
    pthread_mutex_init(&G.lock, NULL);

    G.sr         = cfg ? cfg->sample_rate   : DAW_DEFAULT_SR;
    G.bits       = cfg ? cfg->bit_depth     : 24;
    G.buf_frames = cfg ? cfg->buffer_frames : DAW_DEFAULT_BUFFER;
    G.bpm        = (cfg && cfg->bpm > 0) ? cfg->bpm : DAW_DEFAULT_BPM;
    G.master_vol = 1.0f;
    G.state      = DAW_STATE_STOPPED;

    ma_device_config dcfg       = ma_device_config_init(ma_device_type_playback);
    dcfg.playback.format        = ma_format_f32;
    dcfg.playback.channels      = DAW_CHANNELS;
    dcfg.sampleRate             = G.sr;
    dcfg.periodSizeInFrames     = G.buf_frames;
    dcfg.dataCallback           = audio_cb;

    if (ma_device_init(NULL, &dcfg, &G.device) != MA_SUCCESS)
        return DAW_ERR_AUDIO_DEVICE;

    if (ma_device_start(&G.device) != MA_SUCCESS) {
        ma_device_uninit(&G.device);
        return DAW_ERR_AUDIO_DEVICE;
    }

    G.ready = true;
    fprintf(stdout, "[DAW %s] Init OK | SR=%u bpm=%.1f buf=%u\n",
            DAW_VERSION_STR, G.sr, G.bpm, G.buf_frames);
    return DAW_OK;
}

daw_result_t daw_shutdown(void) {
    if (!G.ready) return DAW_ERR_NOT_INIT;

    ma_device_stop(&G.device);
    ma_device_uninit(&G.device);

    /* Libera clips */
    for (int ti = 0; ti < DAW_MAX_TRACKS; ti++) {
        track_t *t = &G.tracks[ti];
        if (!t->active) continue;
        for (uint32_t ci = 0; ci < t->n_clips; ci++) {
            free(t->clips[ci].l);
            free(t->clips[ci].r);
        }
    }

    pthread_mutex_destroy(&G.lock);
    memset(&G, 0, sizeof(G));
    fprintf(stdout, "[DAW] Shutdown OK\n");
    return DAW_OK;
}

daw_result_t daw_get_state(daw_state_t *out) {
    if (!G.ready) return DAW_ERR_NOT_INIT;
    if (!out)     return DAW_ERR_INVALID_PARAM;

    pthread_mutex_lock(&G.lock);
    out->transport       = G.state;
    out->bpm             = G.bpm;
    out->sample_rate     = G.sr;
    out->bit_depth       = G.bits;
    out->position_beats  = G.pos_beats;
    out->position_seconds= G.pos_secs;
    out->bar             = (uint32_t)(G.pos_beats / 4.0) + 1;
    out->beat            = (uint32_t)fmod(G.pos_beats, 4.0) + 1;
    out->master_volume   = G.master_vol;
    out->master_peak_l   = G.master_peak_l;
    out->master_peak_r   = G.master_peak_r;
    out->track_count     = G.n_tracks;
    out->loop_enabled    = G.loop_on;
    out->loop_start_beat = G.loop_start;
    out->loop_end_beat   = G.loop_end;
    pthread_mutex_unlock(&G.lock);
    return DAW_OK;
}

const char *daw_version(void) { return "BlenderDAW Engine " DAW_VERSION_STR; }

const char *daw_strerror(daw_result_t e) {
    switch (e) {
        case DAW_OK:               return "OK";
        case DAW_ERR_NOT_INIT:     return "engine não iniciado";
        case DAW_ERR_ALREADY_INIT: return "engine já iniciado";
        case DAW_ERR_AUDIO_DEVICE: return "falha no dispositivo de áudio";
        case DAW_ERR_INVALID_TRACK:return "track inválida";
        case DAW_ERR_FILE_NOT_FOUND:return "arquivo não encontrado";
        case DAW_ERR_OUT_OF_MEMORY:return "sem memória";
        case DAW_ERR_INVALID_PARAM:return "parâmetro inválido";
        case DAW_ERR_CLIP_FULL:    return "máximo de clips atingido";
        default:                   return "erro desconhecido";
    }
}

/* ════════════════════════════════════════════════════════════
   TRANSPORT
═══════════════════════════════════════════════════════════════ */

#define NEED_INIT if (!G.ready) return DAW_ERR_NOT_INIT
#define LOCK      pthread_mutex_lock(&G.lock)
#define UNLOCK    pthread_mutex_unlock(&G.lock)

daw_result_t daw_play(void) {
    NEED_INIT;
    LOCK; G.state = DAW_STATE_PLAYING;   UNLOCK; return DAW_OK;
}
daw_result_t daw_stop(void) {
    NEED_INIT;
    LOCK; G.state = DAW_STATE_STOPPED; G.pos_beats = 0; G.pos_secs = 0; UNLOCK;
    return DAW_OK;
}
daw_result_t daw_pause(void) {
    NEED_INIT;
    LOCK;
    if (G.state == DAW_STATE_PLAYING) G.state = DAW_STATE_PAUSED;
    UNLOCK; return DAW_OK;
}
daw_result_t daw_record(void) {
    NEED_INIT;
    LOCK; G.state = DAW_STATE_RECORDING; UNLOCK; return DAW_OK;
}
daw_result_t daw_seek(double beat) {
    NEED_INIT;
    if (beat < 0) return DAW_ERR_INVALID_PARAM;
    LOCK;
    G.pos_beats = beat;
    G.pos_secs  = beat * (60.0 / G.bpm);
    UNLOCK; return DAW_OK;
}
daw_result_t daw_set_bpm(double bpm) {
    NEED_INIT;
    if (bpm < 1 || bpm > 999) return DAW_ERR_INVALID_PARAM;
    LOCK; G.bpm = bpm; UNLOCK; return DAW_OK;
}
daw_result_t daw_set_loop(bool en, double s, double e) {
    NEED_INIT;
    if (s >= e) return DAW_ERR_INVALID_PARAM;
    LOCK; G.loop_on = en; G.loop_start = s; G.loop_end = e; UNLOCK;
    return DAW_OK;
}

/* ════════════════════════════════════════════════════════════
   MASTER
═══════════════════════════════════════════════════════════════ */

daw_result_t daw_set_master_volume(float v) {
    NEED_INIT;
    if (v < 0 || v > 2) return DAW_ERR_INVALID_PARAM;
    LOCK; G.master_vol = v; UNLOCK; return DAW_OK;
}
daw_result_t daw_get_master_peaks(float *l, float *r) {
    NEED_INIT;
    if (!l || !r) return DAW_ERR_INVALID_PARAM;
    *l = G.master_peak_l; *r = G.master_peak_r;
    return DAW_OK;
}

/* ════════════════════════════════════════════════════════════
   TRACKS
═══════════════════════════════════════════════════════════════ */

daw_result_t daw_track_create(daw_track_type_t type, uint32_t *out_id) {
    NEED_INIT;
    if (!out_id || G.n_tracks >= DAW_MAX_TRACKS) return DAW_ERR_OUT_OF_MEMORY;

    LOCK;
    static uint32_t next_id = 1;
    for (int i = 0; i < DAW_MAX_TRACKS; i++) {
        if (G.tracks[i].active) continue;
        track_t *t = &G.tracks[i];
        memset(t, 0, sizeof(*t));
        t->active = true;
        t->id     = next_id++;
        t->type   = type;
        t->vol    = 1.0f;
        t->pan    = 0.0f;
        const char *tn[] = {"Audio","MIDI","Bus","Master"};
        snprintf(t->name, 64, "%s %u", tn[type < 4 ? type : 0], G.n_tracks+1);
        *out_id = t->id;
        G.n_tracks++;
        UNLOCK;
        fprintf(stdout, "[DAW] Track %u criada: '%s'\n", t->id, t->name);
        return DAW_OK;
    }
    UNLOCK;
    return DAW_ERR_OUT_OF_MEMORY;
}

daw_result_t daw_track_destroy(uint32_t id) {
    NEED_INIT;
    LOCK;
    track_t *t = find_track(id);
    if (!t) { UNLOCK; return DAW_ERR_INVALID_TRACK; }
    for (uint32_t ci = 0; ci < t->n_clips; ci++) {
        free(t->clips[ci].l);
        free(t->clips[ci].r);
    }
    t->active = false;
    G.n_tracks--;
    refresh_solo();
    UNLOCK;
    return DAW_OK;
}

daw_result_t daw_track_info(uint32_t id, daw_track_info_t *out) {
    NEED_INIT;
    if (!out) return DAW_ERR_INVALID_PARAM;
    LOCK;
    track_t *t = find_track(id);
    if (!t) { UNLOCK; return DAW_ERR_INVALID_TRACK; }
    out->id        = t->id;
    out->type      = t->type;
    out->volume    = t->vol;
    out->pan       = t->pan;
    out->muted     = t->muted;
    out->soloed    = t->soloed;
    out->armed     = t->armed;
    out->peak_l    = t->peak_l;
    out->peak_r    = t->peak_r;
    out->clip_count= t->n_clips;
    strncpy(out->name, t->name, 63);
    UNLOCK;
    return DAW_OK;
}

daw_result_t daw_track_set_name(uint32_t id, const char *name) {
    NEED_INIT;
    if (!name) return DAW_ERR_INVALID_PARAM;
    LOCK;
    track_t *t = find_track(id);
    if (!t) { UNLOCK; return DAW_ERR_INVALID_TRACK; }
    strncpy(t->name, name, 63);
    UNLOCK; return DAW_OK;
}

daw_result_t daw_track_set_vol(uint32_t id, float v) {
    NEED_INIT;
    LOCK;
    track_t *t = find_track(id);
    if (!t) { UNLOCK; return DAW_ERR_INVALID_TRACK; }
    t->vol = clampf(v, 0.0f, 2.0f);
    UNLOCK; return DAW_OK;
}

daw_result_t daw_track_set_pan(uint32_t id, float p) {
    NEED_INIT;
    LOCK;
    track_t *t = find_track(id);
    if (!t) { UNLOCK; return DAW_ERR_INVALID_TRACK; }
    t->pan = clampf(p, -1.0f, 1.0f);
    UNLOCK; return DAW_OK;
}

daw_result_t daw_track_set_mute(uint32_t id, bool v) {
    NEED_INIT;
    LOCK;
    track_t *t = find_track(id);
    if (!t) { UNLOCK; return DAW_ERR_INVALID_TRACK; }
    t->muted = v;
    UNLOCK; return DAW_OK;
}

daw_result_t daw_track_set_solo(uint32_t id, bool v) {
    NEED_INIT;
    LOCK;
    track_t *t = find_track(id);
    if (!t) { UNLOCK; return DAW_ERR_INVALID_TRACK; }
    t->soloed = v;
    refresh_solo();
    UNLOCK; return DAW_OK;
}

daw_result_t daw_track_set_armed(uint32_t id, bool v) {
    NEED_INIT;
    LOCK;
    track_t *t = find_track(id);
    if (!t) { UNLOCK; return DAW_ERR_INVALID_TRACK; }
    t->armed = v;
    UNLOCK; return DAW_OK;
}

daw_result_t daw_track_load_file(uint32_t id, const char *path) {
    NEED_INIT;
    if (!path) return DAW_ERR_INVALID_PARAM;
    LOCK;
    track_t *t = find_track(id);
    if (!t) { UNLOCK; return DAW_ERR_INVALID_TRACK; }
    if (t->n_clips >= DAW_MAX_CLIPS_PER_TRACK) { UNLOCK; return DAW_ERR_CLIP_FULL; }

    /* ── Decodifica com miniaudio ── */
    ma_decoder_config dcfg = ma_decoder_config_init(ma_format_f32, DAW_CHANNELS, G.sr);
    ma_decoder dec;
    if (ma_decoder_init_file(path, &dcfg, &dec) != MA_SUCCESS) {
        UNLOCK; return DAW_ERR_FILE_NOT_FOUND;
    }

    ma_uint64 total_frames = 0;
    ma_decoder_get_length_in_pcm_frames(&dec, &total_frames);
    if (total_frames == 0) total_frames = G.sr * 30; /* fallback 30s */

    float *ilv = (float *)malloc(sizeof(float) * total_frames * DAW_CHANNELS);
    if (!ilv) { ma_decoder_uninit(&dec); UNLOCK; return DAW_ERR_OUT_OF_MEMORY; }

    ma_uint64 read = 0;
    ma_decoder_read_pcm_frames(&dec, ilv, total_frames, &read);
    ma_decoder_uninit(&dec);

    float *sl = (float *)malloc(sizeof(float) * read);
    float *sr = (float *)malloc(sizeof(float) * read);
    if (!sl || !sr) { free(ilv); free(sl); free(sr); UNLOCK; return DAW_ERR_OUT_OF_MEMORY; }

    for (uint64_t f = 0; f < read; f++) {
        sl[f] = ilv[f * 2 + 0];
        sr[f] = ilv[f * 2 + 1];
    }
    free(ilv);

    clip_t *cl   = &t->clips[t->n_clips];
    cl->l         = sl;
    cl->r         = sr;
    cl->n         = read;
    cl->start_beat= 0.0;
    /* duração em beats: frames ÷ (sr × 60/bpm) — usa bpm atual */
    cl->len_beats = (double)read / ((double)G.sr * 60.0 / G.bpm);
    cl->active    = true;
    t->n_clips++;

    UNLOCK;
    fprintf(stdout, "[DAW] Track %u: '%s' carregado (%llu frames)\n",
            id, path, (unsigned long long)read);
    return DAW_OK;
}

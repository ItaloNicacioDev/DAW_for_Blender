# Créditos e Licenças de Terceiros

O código deste addon é de autoria de **Italo Nicacio Dev** (ver
`LICENSE.md`). Este arquivo documenta especificamente os **arquivos de
áudio** (`.wav`) incluídos em `daw/assets/samples/`, que são de
terceiros e regidos pela licença original da fonte, não pela licença
do addon.

> ⚠️ Isto não é aconselhamento jurídico — é um registro de procedência
> dos assets usados neste addon.

## Fonte: Free Wave Samples (freewavesamples.com)

Todos os samples reais usados neste addon (instrumentos e tambores)
foram obtidos em **freewavesamples.com**.

**Licença** (conforme página "About Us / License" do site):
os samples são disponibilizados como *freeware*, de uso royalty-free.
Atribuição/crédito ao site é apreciada mas não é obrigatória. O site
proíbe hospedar cópias dos arquivos para download direto em outro
lugar, **mas abre exceção explícita quando os samples são usados como
parte funcional de uma aplicação de software** (o próprio site cita
"virtual drum machine" como exemplo) — que é exatamente o caso deste
addon: os `.wav` não são oferecidos para download avulso, são ativos
internos usados pela função de reprodução de som do Piano Roll e do
Beat Grid.

Fonte / licença completa: https://freewavesamples.com/about-us-license

## Amostras de Instrumento — `assets/samples/instruments/`

| Arquivo | Instrumento | Fonte |
|---|---|---|
| `0_acoustic_piano.wav` | Acoustic Piano | freewavesamples.com |
| `1_electric_piano.wav` | Electric Piano | freewavesamples.com |
| `2_strings.wav` | Strings | freewavesamples.com |
| `3_organ.wav` | Organ | freewavesamples.com |
| `4_bass.wav` | Bass | freewavesamples.com |
| `5_synth_lead.wav` | Synth Lead | freewavesamples.com |
| `6_vibraphone.wav` | Vibraphone | *não incluído — usa síntese interna* |
| `7_choir.wav` | Choir | *não incluído — usa síntese interna* |

## Amostras de Bateria — `assets/samples/drums/`

| Arquivo | Tambor | Fonte |
|---|---|---|
| `kick.wav` | Kick | freewavesamples.com |
| `clap.wav` | Clap | freewavesamples.com |
| `hihat.wav` | Hi-Hat | freewavesamples.com |
| `snare.wav` | Snare | freewavesamples.com |
| `openhat.wav` | Open Hat | freewavesamples.com |
| `tom.wav` | Tom | freewavesamples.com |
| `perc.wav` | Perc | freewavesamples.com |
| `ride.wav` | Ride | *não incluído — usa síntese interna* |

## Sons sintéticos (sem terceiros)

Os slots sem sample real (`vibraphone`, `choir`, `ride`) e todo o
fallback de síntese usado quando um sample não é encontrado são
gerados **inteiramente por código** (síntese aditiva em
`daw/ui/piano_roll.py` e `daw/ui/beat_grid.py`), sem uso de nenhum
material de terceiros — cobertos normalmente pela licença do addon em
`LICENSE.md`.
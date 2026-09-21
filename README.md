# DAW for Blender  (beta)

Uma DAW (estação de trabalho de áudio) que roda dentro do Blender: mixer,
channel rack, patterns, piano roll, playlist, sampler, gravação, automação,
efeitos, exportação e host de plugins VST3.

> **Status: beta.** Veja "O que funciona / limitações" antes de usar em produção.

## Requisitos

- **Blender 4.5+**
- **Windows** para plugins **VST3**. Em macOS/Linux o resto da DAW carrega
  normalmente, mas o host VST fica desativado (o painel VST avisa).
- Opcional, para gravação e monitor ao vivo: `sounddevice` (o Blender não o traz).
  Instale no Python do Blender:

  ```
  <pasta_do_blender>/python/bin/python -m pip install sounddevice
  ```

  Alguns recursos do módulo Browser (miniaturas/preview) usam `soundfile` e `Pillow`.

## Instalação

1. Gere o pacote: `python tools/build_release.py` (cria `dist/daw-<versão>.zip`),
   ou compacte a pasta `daw/` inteira num `.zip`.
2. Blender → Edit → Preferences → Add-ons → Install from Disk… → escolha o `.zip`.
3. Ative **Blender DAW**. O workspace "DAW" e o Application Template são criados
   automaticamente.

## O que funciona / limitações

| Área | Estado |
|---|---|
| Transporte, timeline, playlist, patterns, piano roll, channel rack | Funcional |
| Mixer (volume, pan, mute, solo, sends, buses, presets) | Funcional |
| Salvar/carregar projeto (`.json`) | Mixer, patterns, piano roll, playlist, VST e **automação**. Channel rack, sampler e metrônomo ainda **não** entram no `.json` |
| **Efeitos internos** (EQ, Compressor, Limiter, Reverb, Delay, Chorus, Flanger, Phaser, Distorção) | Processam áudio de verdade, mas de forma **offline (bounce)**, não em tempo real — veja abaixo |
| **Automação** | Aplica `master.volume`, `channel.N.volume/pan/mute` (ou `volume`/`pan`/`mute` da faixa ativa) durante a reprodução. **Não** automatiza parâmetros de efeitos/instrumentos ainda |
| VST3 | Só Windows. O plugin roda **dentro do processo do Blender**: se ele travar, o Blender fecha. Salve com frequência |
| Módulo Browser | Ainda sem interface (desativado) |

### Como usar os efeitos internos

Os efeitos não rodam em tempo real durante o play. Em vez disso:

1. Adicione os efeitos na cadeia da faixa (painel **Mixer → Inserts**) ou do
   canal (painel **Efeitos**).
2. Clique em **Aplicar Inserts a uma Strip** (ou **Aplicar Efeitos a uma Strip**)
   e escolha a strip de áudio.
3. O áudio processado vira uma nova strip (com a cauda de delay/reverb) e a
   original é mutada. Nada é apagado.

Os efeitos são feitos só com numpy (o Blender não traz scipy), em `modules/effects/dsp.py`.

## Testes

Os testes rodam **fora do Blender**:

```
pip install numpy pytest
python -m pytest
```

Cobrem o DSP, a persistência/aplicação da automação, o parser de versões do
updater e a proteção contra falha de import do host VST fora do Windows.

## Licença

Veja `LICENSE.md` e `THIRD-PARTY-LICENSES.md` (samples de freewavesamples.com).
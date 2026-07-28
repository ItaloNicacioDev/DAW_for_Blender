# Créditos e Licenças de Terceiros

O código deste addon é de autoria de **Italo Nicacio Dev** (ver
`LICENSE.md`). Este arquivo documenta especificamente os **arquivos de
áudio** (`.wav`) incluídos em `daw/assets/samples/`, que são de
terceiros e regidos pelas licenças originais das respectivas fontes,
não pela licença do addon.

> ⚠️ Isto não é aconselhamento jurídico. As tabelas abaixo têm campos
> em branco (`_preencher_`) para você registrar exatamente de onde
> baixou cada arquivo. Recomendo preencher isso agora, enquanto está
> fresco, e guardar um print/link da página de origem de cada sample —
> isso serve como prova de licenciamento caso precise no futuro.

## Fonte principal: Free Wave Samples (freewavesamples.com)

**Resumo da licença** (conforme página "About Us / License" do site,
consultada em 2026): os samples são disponibilizados como *freeware*,
de uso royalty-free. Atribuição/crédito ao site é apreciada mas não é
obrigatória. O ponto mais importante para este projeto: o site proíbe
hospedar cópias dos arquivos para download direto em outro site, **mas
abre exceção explícita para o caso de os samples serem usados como
parte funcional de uma aplicação de software** (o próprio site cita
como exemplo "virtual drum machine") — que é exatamente o caso deste
addon: os `.wav` não são oferecidos para download avulso, são ativos
internos usados pela função de reprodução de som do Piano Roll e do
Beat Grid.

Fonte: https://freewavesamples.com/about-us-license

## Amostras de Instrumento — `assets/samples/instruments/`

| Arquivo | Instrumento | Página de origem (freewavesamples.com) | Observação |
|---|---|---|---|
| `0_acoustic_piano.wav` | Acoustic Piano | https://freewavesamples.com/about-us-license *(link geral — ver nota)* | |
| `1_electric_piano.wav` | Electric Piano | https://freewavesamples.com/about-us-license *(link geral — ver nota)* | |
| `2_strings.wav` | Strings | https://freewavesamples.com/about-us-license *(link geral — ver nota)* | |
| `3_organ.wav` | Organ | https://freewavesamples.com/about-us-license *(link geral — ver nota)* | |
| `4_bass.wav` | Bass | https://freewavesamples.com/about-us-license *(link geral — ver nota)* | |
| `5_synth_lead.wav` | Synth Lead | https://freewavesamples.com/about-us-license *(link geral — ver nota)* | |
| `6_vibraphone.wav` | Vibraphone | *não incluído — usa síntese interna* | — |
| `7_choir.wav` | Choir | *não incluído — usa síntese interna* | — |

## Amostras de Bateria — `assets/samples/drums/`

| Arquivo | Tambor | Página de origem (freewavesamples.com) | Observação |
|---|---|---|---|
| `kick.wav` | Kick | https://freewavesamples.com/about-us-license *(link geral — ver nota)* | |
| `clap.wav` | Clap | https://freewavesamples.com/about-us-license *(link geral — ver nota)* | |
| `hihat.wav` | Hi-Hat | https://freewavesamples.com/about-us-license *(link geral — ver nota)* | |
| `snare.wav` | Snare | https://freewavesamples.com/about-us-license *(link geral — ver nota)* | |
| `openhat.wav` | Open Hat | https://freewavesamples.com/about-us-license *(link geral — ver nota)* | |
| `tom.wav` | Tom | https://freewavesamples.com/about-us-license *(link geral — ver nota)* | |
| `perc.wav` | Perc | https://freewavesamples.com/about-us-license *(link geral — ver nota)* | |
| `ride.wav` | Ride | *não incluído — usa síntese interna* | — |

## Como preencher

O link que você me passou (`https://freewavesamples.com/about-us-license`)
é a página **geral** de licença do site — por isso preenchi as tabelas
acima com ele como referência provisória de licenciamento. Ele já é
suficiente para comprovar sob qual licença os samples foram obtidos.
Se quiser reforçar ainda mais (recomendado, mas opcional), depois volte
em cada página específica do instrumento/tambor (ex: a página de
"Vibraphone" ou "Kick Drum" no site) e substitua pelo link exato — isso
deixa rastreável exatamente qual arquivo veio de qual página, caso
precise no futuro.

Pra cada arquivo, volte na página do freewavesamples.com de onde você
baixou o `.wav` e cole o link na coluna correspondente. Se algum
arquivo veio de outra fonte (ex: você trocou por Univ. Iowa, 99Sounds
ou VSCO2-CE em algum slot), me avisa que eu ajusto a tabela e o resumo
de licença dessa fonte específica também.

## Sons sintéticos (sem terceiros)

Os slots sem sample real (`vibraphone`, `choir`, `ride`) e todo o
fallback de síntese usado quando um sample não é encontrado são
gerados **inteiramente por código** (síntese aditiva em
`daw/ui/piano_roll.py` e `daw/ui/beat_grid.py`), sem uso de nenhum
material de terceiros — cobertos normalmente pela licença do addon em
`LICENSE.md`.
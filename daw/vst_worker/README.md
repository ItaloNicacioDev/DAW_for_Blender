# Setup do worker de VST (isolado da versão de Python do Blender)

Este addon roda o `dawdreamer` de verdade **fora** do processo do
Blender, num Python embutido à parte. Isso resolve dois problemas de
uma vez:

1. Não depende de o Blender e o `dawdreamer` usarem a mesma versão de
   Python (hoje, ago/2026, o `dawdreamer` não tem build oficial para
   Python 3.13, que é o que o Blender 5.2 usa).
2. Se um VST travar/crashar, só o processo worker morre — o Blender
   continua de pé.

## Passo a passo (Windows)

1. Baixe o **Python 3.12 embeddable package (64-bit)** em
   https://www.python.org/downloads/windows/ (procure por
   "Windows embeddable package (64-bit)" na versão 3.12.x).

2. Extraia o `.zip` para:
   ```
   daw/vendor/py312_embed_win_amd64/
   ```
   (a pasta deve conter `python.exe` na raiz)

3. Habilite o `pip` nesse Python embutido:
   - Abra o arquivo `python312._pth` dentro da pasta extraída e
     descomente a linha `#import site` (remova o `#`).
   - Baixe `get-pip.py` (https://bootstrap.pypa.io/get-pip.py) e rode:
     ```
     daw\vendor\py312_embed_win_amd64\python.exe get-pip.py
     ```

4. Instale as dependências do worker **dentro desse Python embutido**
   (não no Python do Blender):
   ```
   daw\vendor\py312_embed_win_amd64\python.exe -m pip install dawdreamer numpy
   ```

5. Teste que o worker sobe sozinho:
   ```
   daw\vendor\py312_embed_win_amd64\python.exe daw\vst_worker\worker.py
   ```
   Deve imprimir algo como `DAW-VST-WORKER PORT=54321` e ficar parado
   esperando conexão — é o addon quem conecta automaticamente na
   primeira vez que você carregar um VST. Feche com Ctrl+C.

Pronto — a partir daqui o addon detecta e sobe o worker sozinho (ver
`modules/vst/ipc_engine.py`, `find_worker_python()`).

## macOS / Linux

Mesma ideia, trocando a pasta de destino:

- macOS Apple Silicon: `daw/vendor/py312_embed_macos_arm64/`
- macOS Intel: `daw/vendor/py312_embed_macos_x86_64/`
- Linux x86_64: `daw/vendor/py312_embed_linux_x86_64/`

Como essas plataformas não têm um "embeddable package" oficial como o
Windows, o caminho mais simples é criar um venv normal com
`python3.12 -m venv` e apontar `_worker_python_candidates()` em
`ipc_engine.py` para `bin/python3` dentro dele (já é o padrão hoje).
Depois só rodar:
```
./bin/python3 -m pip install dawdreamer numpy
```
dentro dessa venv.

## Por que isso é mais duradouro que vendorizar um `.pyd`

Quando o Blender atualizar de Python de novo no futuro (vai
acontecer), **nada aqui precisa mudar** — o worker continua rodando
no Python 3.12 dele, isolado. O único ponto de atenção é: se um dia o
`dawdreamer` parar de suportar 3.12 (não vai tão cedo), é só repetir
este mesmo processo com a versão de Python que ele passar a suportar
e atualizar a pasta em `daw/vendor/`.
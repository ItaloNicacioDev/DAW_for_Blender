# modules/recorder/input.py
"""
Gerenciamento de dispositivos de entrada de áudio.

[FIX v2] Dispositivos reais via aud.Device (nativo do Blender, sem dependências
externas). sounddevice é tentado como alternativa para captura de stream em tempo
real, mas a listagem de dispositivos sempre funciona via aud, que já vem instalado
no Python embutido do Blender.

[FIX v3] Corrige um bug real: o identificador salvo no EnumProperty
(`input_device`/`output_device`, em modules/settings/preferences.py) é o
ÍNDICE do dispositivo na lista do sounddevice (ex.: "3"), não o nome --
mas `InputDeviceManager.start()` comparava `dev['name'] == device_name`,
que nunca batia com um índice numérico. Resultado: o dispositivo
selecionado na UI nunca era usado de verdade, sempre caía no default do
sistema. `resolve_device_index()` resolve isso corretamente.

[FIX v3] Também unifica a seleção de dispositivo: antes existia uma cópia
redundante de `input_device`/`output_device` em
`modules/recorder/properties.py` (por projeto/Scene) além da cópia em
`modules/settings/preferences.py` (global, AddonPreferences) -- as duas
listavam os MESMOS dispositivos e ficavam fora de sincronia uma da
outra. Agora só existe uma fonte de verdade: as preferências globais do
addon. `get_default_input_identifier()`/`get_default_output_identifier()`
abaixo são o único lugar que o resto do addon deveria consultar.

Estratégia:
  - Listagem de dispositivos: sounddevice (detalhado, com host API) se
    disponível; aud como fallback (sempre presente no Blender, porém
    sem diferenciar entrada/saída nem host API).
  - Captura de stream em tempo real: sounddevice (se instalado).
  - Fallback: buffer de zeros com aviso claro na UI.
"""
from __future__ import annotations

from typing import Optional

import numpy as np


# ═══════════════════════════════════════════════════════════════
#  LISTAGEM DE DISPOSITIVOS VIA aud  [FIX v2]
#
#  Problema original: get_devices() dependia exclusivamente de
#  sounddevice, que não está instalado no Python embutido do Blender.
#  Quando falhava a importação, retornava lista com item de erro e
#  não havia nenhum caminho alternativo.
#
#  Solução: aud.Device() já tem acesso ao backend de áudio do Blender
#  (OpenAL / SDL). Usamos aud para listar os dispositivos disponíveis
#  no sistema. sounddevice é usado como segunda opção para captura
#  de stream — se não estiver instalado, retorna buffer de zeros e
#  exibe aviso claro.
# ═══════════════════════════════════════════════════════════════

def _list_devices_via_aud():
    """
    Lista dispositivos de saída/entrada via aud (Audaspace — nativo do Blender).
    Retorna lista de tuplas (idx_str, nome, descrição) compatível com EnumProperty.
    """
    items = []
    try:
        import aud
        # aud.Device.list() retorna lista de nomes de dispositivos disponíveis.
        # Se a versão do Blender não tiver Device.list(), usa fallback com
        # o dispositivo padrão.
        device_list = None
        try:
            device_list = aud.Device.list()
        except AttributeError:
            # Blender < 3.4 ou build sem Device.list() — tenta names()
            try:
                device_list = aud.Device.names()
            except AttributeError:
                device_list = None

        if device_list:
            for idx, name in enumerate(device_list):
                label = name if name else f"Dispositivo {idx}"
                items.append((str(idx), label, f"[aud] {label}"))
        else:
            # Fallback: pelo menos o Default funciona sempre
            items.append(('0', 'Default (Sistema)', '[aud] Dispositivo padrão do sistema'))

    except ImportError:
        items.append(('-1', 'aud indisponível', 'Módulo aud não encontrado'))
    except Exception as e:
        items.append(('-1', f'Erro: {str(e)[:40]}', str(e)))

    return items if items else [('-1', 'Nenhum dispositivo', 'Sem dispositivos de áudio')]


def _list_devices_via_sounddevice():
    """
    Lista dispositivos via sounddevice (requer instalação no Python do Blender).
    Retorna (entrada, saída) — cada um é lista de tuplas (idx_str, nome, desc).

    O idx_str usado como identificador do EnumProperty é o ÍNDICE do
    dispositivo em `sounddevice.query_devices()` -- é isso que
    `resolve_device_index()` espera receber de volta.
    """
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        try:
            hostapis = sd.query_hostapis()
        except Exception:
            hostapis = []

        inputs  = []
        outputs = []
        for idx, dev in enumerate(devices):
            name = dev['name']
            hostapi_name = ""
            try:
                hostapi_name = hostapis[dev['hostapi']]['name']
            except Exception:
                pass
            suffix = f" [{hostapi_name}]" if hostapi_name else ""
            if dev['max_input_channels'] > 0:
                inputs.append((str(idx), name,
                               f"{name}{suffix} [in:{dev['max_input_channels']}ch]"))
            if dev['max_output_channels'] > 0:
                outputs.append((str(idx), name,
                                f"{name}{suffix} [out:{dev['max_output_channels']}ch]"))
        return inputs, outputs
    except ImportError:
        return None, None
    except Exception as e:
        print(f"[DAW Recorder] sounddevice.query_devices: {e}")
        return None, None


def get_input_devices():
    """
    Retorna lista de dispositivos de ENTRADA disponíveis.
    Tenta sounddevice primeiro (mais detalhado); cai para aud se não instalado.
    """
    sd_inputs, _ = _list_devices_via_sounddevice()
    if sd_inputs is not None:
        return sd_inputs if sd_inputs else [('-1', 'Nenhum', 'Sem entradas detectadas')]

    # sounddevice não disponível: usa aud (lista saídas, que inclui Default)
    aud_devs = _list_devices_via_aud()
    # Marca como entrada genérica (aud não diferencia in/out em Device.list())
    return [(idx, name, f"(entrada) {desc}") for idx, name, desc in aud_devs]


def get_output_devices():
    """
    Retorna lista de dispositivos de SAÍDA disponíveis.
    Tenta sounddevice primeiro; cai para aud se não instalado.
    """
    _, sd_outputs = _list_devices_via_sounddevice()
    if sd_outputs is not None:
        return sd_outputs if sd_outputs else [('-1', 'Nenhum', 'Sem saídas detectadas')]

    return _list_devices_via_aud()


# ═══════════════════════════════════════════════════════════════
#  RESOLUÇÃO DE ÍNDICE  [FIX v3]
# ═══════════════════════════════════════════════════════════════

def resolve_device_index(identifier) -> Optional[int]:
    """
    Converte o identificador salvo no EnumProperty (string do índice em
    `sounddevice.query_devices()`, ou 'Default'/'-1'/vazio) num índice
    inteiro válido pra passar em `sounddevice.Stream(device=...)`.
    Retorna None pra usar o dispositivo padrão do sistema -- tanto
    quando o identificador pede explicitamente o default quanto quando
    o índice salvo não existe mais (ex.: dispositivo foi desconectado
    desde a última vez que a lista foi gerada).
    """
    if identifier in (None, "Default", "-1", "", "erro"):
        return None
    try:
        idx = int(identifier)
    except (TypeError, ValueError):
        return None
    try:
        import sounddevice as sd
        if 0 <= idx < len(sd.query_devices()):
            return idx
    except Exception:
        pass
    return None


def get_default_input_identifier() -> str:
    """Fonte única de verdade pro dispositivo de entrada configurado
    globalmente (modules/settings/preferences.py -> DAW_PreferencesAudio).
    Import tardio pra evitar import circular entre os dois módulos."""
    try:
        from ..settings.preferences import get_preferences
        return get_preferences().audio.input_device
    except Exception:
        return "Default"


def get_default_output_identifier() -> str:
    """Equivalente de saída de `get_default_input_identifier()`."""
    try:
        from ..settings.preferences import get_preferences
        return get_preferences().audio.output_device
    except Exception:
        return "Default"


# ═══════════════════════════════════════════════════════════════
#  DIAGNÓSTICO E RECOMENDAÇÃO DE DRIVER
# ═══════════════════════════════════════════════════════════════

def get_audio_diagnostics() -> dict:
    """
    Diagnóstico do estado atual do áudio no Python do Blender: se
    sounddevice está instalado, se algum host API ASIO foi detectado, e
    uma recomendação textual pronta pra mostrar na UI quando o
    dispositivo físico do usuário não aparece na lista ou quando não há
    ASIO disponível (latência mais alta, sem acesso exclusivo ao
    hardware).

    Retorna:
        {
            "has_sounddevice": bool,
            "has_asio_hostapi": bool,
            "hostapis": [nomes...],
            "recommendation": str | None,  # None = tudo certo, nada a avisar
        }
    """
    diag = {
        "has_sounddevice": False,
        "has_asio_hostapi": False,
        "hostapis": [],
        "recommendation": None,
    }

    try:
        import sounddevice as sd
    except Exception:
        diag["recommendation"] = (
            "sounddevice não está instalado no Python do Blender -- a lista de "
            "dispositivos abaixo é limitada (via aud, sem detalhes de canais/driver). "
            "Instale sounddevice pra ver todos os dispositivos de verdade e poder "
            "gravar:\n"
            "    <pasta_do_blender>\\python\\bin\\python.exe -m pip install sounddevice"
        )
        return diag

    diag["has_sounddevice"] = True
    try:
        hostapis = sd.query_hostapis()
        diag["hostapis"] = [h["name"] for h in hostapis]
        diag["has_asio_hostapi"] = any("ASIO" in h["name"].upper() for h in hostapis)
    except Exception:
        pass

    if not diag["has_asio_hostapi"]:
        diag["recommendation"] = (
            "Nenhum driver ASIO detectado no sistema. Se sua interface de áudio "
            "não aparecer na lista abaixo, ou você quiser latência mais baixa e "
            "acesso exclusivo ao hardware (recomendado pra gravação/monitoramento "
            "sério), instale um driver ASIO:\n"
            "  - ASIO4ALL: driver universal, funciona com quase qualquer placa/interface\n"
            "  - FlexASIO: alternativa open-source baseada em PortAudio\n"
            "Depois de instalar, clique em 'Atualizar Dispositivos' -- o driver ASIO "
            "aparece como um host API novo na lista, geralmente com menor latência "
            "que MME/WDM/DirectSound."
        )
    return diag


# ═══════════════════════════════════════════════════════════════
#  INPUT DEVICE MANAGER
# ═══════════════════════════════════════════════════════════════

class InputDeviceManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.stream = None
        self.device_identifier = "Default"
        self.sample_rate = 48000
        self.channels = 1
        self.blocksize = 1024
        self.dtype = 'float32'
        self.last_buffer = np.zeros(self.blocksize, dtype=self.dtype)
        self.peak_level = 0.0
        self.rms_level = 0.0
        self._callback_count = 0
        # [FIX v2] Indica se sounddevice está disponível para captura real
        self.has_sounddevice = False
        self._check_sounddevice()

    def _check_sounddevice(self):
        try:
            import sounddevice  # noqa: F401
            self.has_sounddevice = True
        except ImportError:
            self.has_sounddevice = False
            print("[DAW Recorder] sounddevice não instalado — captura em tempo real "
                  "desativada. Para ativar: instale sounddevice no Python do Blender.\n"
                  "  Exemplo (Windows): <blender_dir>/python/bin/python.exe -m pip install sounddevice\n"
                  "  A listagem de dispositivos funciona normalmente via aud.")
        except OSError as e:
            # [FIX] O pacote sounddevice pode estar instalado (import ok)
            # mas a lib nativa PortAudio não estar presente no sistema
            # (ex.: Linux sem libportaudio2, ou Windows sem a DLL
            # correta) -- nesse caso sounddevice levanta OSError na
            # importação, não ImportError, e antes isso não era pego:
            # qualquer chamada a start() explodia com um traceback feio
            # em vez de cair no fallback de buffer de zeros com aviso.
            self.has_sounddevice = False
            print(f"[DAW Recorder] sounddevice instalado, mas indisponível ({e}) — "
                  "captura em tempo real desativada. Verifique se a biblioteca nativa "
                  "PortAudio está instalada no sistema (ex.: 'apt install libportaudio2' "
                  "no Linux).")

    def _audio_callback(self, indata, frames, time_info, status):
        if indata is not None and len(indata) > 0:
            self.last_buffer = indata[:, 0].copy() if indata.ndim > 1 else indata.copy()
            self.peak_level = float(np.max(np.abs(self.last_buffer)))
            self.rms_level = float(np.sqrt(np.mean(self.last_buffer ** 2)))
            self._callback_count += 1

    def get_devices(self):
        """
        Retorna lista de dispositivos de entrada.
        [FIX v2] Usa aud como fallback quando sounddevice não está instalado.
        """
        return get_input_devices()

    def start(self, device_identifier: Optional[str] = None, samplerate: int = 48000) -> bool:
        """
        Inicia stream de captura.

        `device_identifier`: mesmo identificador salvo no EnumProperty
            (índice como string, ou None/'Default'). Se None, usa
            `get_default_input_identifier()` -- ou seja, a configuração
            global do addon (Preferências > Áudio > Entrada), que é a
            ÚNICA fonte de verdade agora [FIX v3] (antes cada painel
            podia ter seu próprio dispositivo configurado
            separadamente, e ficavam fora de sincronia).

        [FIX v2] Se sounddevice não estiver disponível, loga aviso claro
        em vez de falhar silenciosamente.
        """
        if not self.has_sounddevice:
            print("[DAW Recorder] Captura em tempo real requer sounddevice. "
                  "Instale no Python interno do Blender para ativar gravação.")
            return False

        if device_identifier is None:
            device_identifier = get_default_input_identifier()
        self.device_identifier = device_identifier

        try:
            import sounddevice as sd
            device_id = resolve_device_index(device_identifier)  # [FIX v3]

            self.stream = sd.InputStream(
                device=device_id,
                channels=self.channels,
                samplerate=samplerate,
                blocksize=self.blocksize,
                dtype=self.dtype,
                callback=self._audio_callback,
            )
            self.stream.start()
            label = device_id if device_id is not None else "Default (sistema)"
            print(f"[DAW Recorder] Stream iniciado: device={label} @ {samplerate}Hz")
            return True
        except Exception as e:
            print(f"[DAW Recorder] Erro ao iniciar entrada: {e}")
            return False

    def stop(self):
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                print(f"[DAW Recorder] Erro ao parar entrada: {e}")
            finally:
                self.stream = None

    def get_levels(self):
        return self.peak_level, self.rms_level

    def read_buffer(self):
        return self.last_buffer.copy()


def get_input_manager() -> InputDeviceManager:
    return InputDeviceManager()


classes = []


def register():
    pass


def unregister():
    mgr = get_input_manager()
    mgr.stop()
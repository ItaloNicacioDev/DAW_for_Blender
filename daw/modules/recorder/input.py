# modules/recorder/input.py
"""
Gerenciamento de dispositivos de entrada de áudio.

[FIX v2] Dispositivos reais via aud.Device (nativo do Blender, sem dependências
externas). sounddevice é tentado como alternativa para captura de stream em tempo
real, mas a listagem de dispositivos sempre funciona via aud, que já vem instalado
no Python embutido do Blender.

Estratégia:
  - Listagem de dispositivos: aud.Device (sempre disponível no Blender)
  - Captura de stream em tempo real: sounddevice (se instalado)
  - Fallback: buffer de zeros com aviso claro na UI
"""
from __future__ import annotations

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
    """
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        inputs  = []
        outputs = []
        for idx, dev in enumerate(devices):
            name = dev['name']
            if dev['max_input_channels'] > 0:
                inputs.append((str(idx), name,
                               f"{name} [in:{dev['max_input_channels']}ch]"))
            if dev['max_output_channels'] > 0:
                outputs.append((str(idx), name,
                                f"{name} [out:{dev['max_output_channels']}ch]"))
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
        self.device_name = "Default"
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

    def start(self, device_name: str = "Default", samplerate: int = 48000):
        """
        Inicia stream de captura.
        [FIX v2] Se sounddevice não estiver disponível, loga aviso claro
        em vez de falhar silenciosamente.
        """
        if not self.has_sounddevice:
            print("[DAW Recorder] Captura em tempo real requer sounddevice. "
                  "Instale no Python interno do Blender para ativar gravação.")
            return False

        try:
            import sounddevice as sd
            device_id = None
            if device_name not in ("Default", "-1", ""):
                devices = sd.query_devices()
                for idx, dev in enumerate(devices):
                    if dev['name'] == device_name and dev['max_input_channels'] > 0:
                        device_id = idx
                        break

            self.stream = sd.InputStream(
                device=device_id,
                channels=self.channels,
                samplerate=samplerate,
                blocksize=self.blocksize,
                dtype=self.dtype,
                callback=self._audio_callback,
            )
            self.stream.start()
            print(f"[DAW Recorder] Stream iniciado: {device_name or 'Default'} @ {samplerate}Hz")
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
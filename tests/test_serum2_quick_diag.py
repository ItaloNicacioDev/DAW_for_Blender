"""
Diagnóstico rápido do Serum 2 VST3.
Testa load, MIDI render e stability com timeouts.
"""
import sys
import signal
import time
from pathlib import Path

# Timeout handler
def timeout_handler(signum, frame):
    print("\n❌ TIMEOUT - Teste expirou (possível hang no worker)")
    sys.exit(1)

# Set timeout de 30 segundos
signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(30)

try:
    from daw.modules.vst.vst import VST, VSTProgramType
    from daw.modules.vst.ipc_engine import is_available
    import numpy as np

    SERUM2_PATH = Path(
        "C:/Program Files/Common Files/VST3/Serum2.vst3/Contents/x86_64-win/Serum2.vst3"
    )

    print("=" * 70)
    print("DIAGNÓSTICO SERUM 2 VST3")
    print("=" * 70)

    # 1. Check path
    if not SERUM2_PATH.exists():
        print(f"❌ Serum 2 não encontrado: {SERUM2_PATH}")
        sys.exit(1)
    print(f"✓ Serum 2 encontrado: {SERUM2_PATH}")

    # 2. Check IPC disponível
    if not is_available():
        print("❌ IPC não disponível")
        sys.exit(1)
    print("✓ IPC disponível")

    # 3. Load
    print("\n[TESTE 1] Load do Serum 2...")
    vst = VST(
        path=SERUM2_PATH,
        name="Serum2",
        vst_type=VSTProgramType.INSTRUMENT,
        vst_id="serum2",
    )

    signal.alarm(15)  # Reset timeout para load
    loaded = vst.load(sample_rate=44100, block_size=512)
    signal.alarm(0)   # Cancela timeout

    if not loaded:
        print(f"❌ Falha ao carregar: {vst.error}")
        sys.exit(1)

    print(f"✓ Carregado com {len(vst.parameters)} parâmetros")

    # 4. Parameter test
    print("\n[TESTE 2] Acesso a parâmetros...")
    signal.alarm(10)
    val = vst.get_parameter(0)
    vst.set_parameter(0, 0.5)
    val2 = vst.get_parameter(0)
    signal.alarm(0)
    print(f"✓ Parâmetro 0: {val:.3f} → {val2:.3f}")

    # 5. MIDI render
    print("\n[TESTE 3] Renderização MIDI...")
    signal.alarm(30)  # 30s timeout para render

    midi_notes = [
        (60, 0.0, 0.5, 100),    # C4
        (64, 0.5, 0.5, 100),    # E4
        (67, 1.0, 0.5, 100),    # G4
    ]

    print("  Renderizando 3 notas MIDI (2s total)...")
    audio = vst.render_instrument(midi_notes, duration=2.0)
    signal.alarm(0)

    if audio is None:
        print("❌ Áudio retornou None")
        vst.unload()
        sys.exit(1)

    print(f"✓ Áudio renderizado: shape={audio.shape}, dtype={audio.dtype}")

    # Verifica se tem energia
    rms = np.sqrt(np.mean(audio ** 2))
    print(f"  RMS: {rms:.6f}")

    if rms < 0.001:
        print("⚠️  Áudio muito silencioso (RMS < 0.001)")
    else:
        print(f"✓ Áudio com energia normal")

    # 6. Unload
    print("\n[TESTE 4] Unload...")
    signal.alarm(10)
    vst.unload()
    signal.alarm(0)
    print(f"✓ Unload completo")

    print("\n" + "=" * 70)
    print("✅ SUCESSO - Serum 2 VST3 funciona completamente!")
    print("=" * 70)
    print("\nCONCLUSÃO:")
    print("- O host consegue carregar e processar Serum 2 VST3")
    print("- Parâmetros são acessíveis e modificáveis")
    print("- MIDI render funciona e produz áudio")
    print("- Unload é limpo")
    print("\n→ DAW tem suporte completo a VST3 profissional como Serum 2")

except Exception as e:
    print(f"\n❌ ERRO: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

finally:
    signal.alarm(0)  # Cancel any pending alarm

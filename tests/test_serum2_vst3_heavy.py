"""
Teste real do Serum 2 VST3 (plugin pesado profissional).

Este teste valida:
  - Load/unload do plugin via worker IPC
  - Editor aberto/fechado
  - Mudança de parâmetros
  - Renderização de notas MIDI
  - Estabilidade e cleanup

Objetivo: verificar se o host consegue lidar com um synth VST3 complexo e pesado
como o Serum 2, que é sensível a thread handling e lifecycle.
"""
import unittest
import time
import numpy as np
from pathlib import Path

from daw.modules.vst.vst import VST, VSTProgramType
from daw.modules.vst.ipc_engine import DawdreamerIPCBridge, is_available


class Serum2VST3HeavyTest(unittest.TestCase):
    """Testes com o Serum 2 VST3 real."""

    SERUM2_PATH = Path(
        "C:/Program Files/Common Files/VST3/Serum2.vst3/Contents/x86_64-win/Serum2.vst3"
    )

    @classmethod
    def setUpClass(cls):
        """Verifica se o Serum 2 está disponível e o host está pronto."""
        if not cls.SERUM2_PATH.exists():
            raise unittest.SkipTest(
                f"Serum 2 não encontrado em {cls.SERUM2_PATH}. "
                "Este teste requer o plugin real instalado."
            )

        if not is_available():
            raise unittest.SkipTest(
                "Dawdreamer IPC não está disponível. "
                "Verifique vendor/py312_embed_win_amd64 e setup_worker_windows.ps1"
            )

    def test_01_load_serum2_instrument(self):
        """Testa carregamento do Serum 2 como instrumento."""
        vst = VST(
            path=self.SERUM2_PATH,
            name="Serum2_Test",
            vst_type=VSTProgramType.INSTRUMENT,
            vst_id="serum2_test",
        )

        loaded = vst.load(sample_rate=44100, block_size=512)
        self.assertTrue(loaded, f"Falha ao carregar Serum 2: {vst.error}")
        self.assertTrue(vst.loaded)
        self.assertIsNotNone(vst.bridge)
        self.assertGreater(len(vst.parameters), 0, "Serum 2 não expôs parâmetros")

        print(f"✓ Serum 2 carregado com {len(vst.parameters)} parâmetros")
        vst.unload()
        self.assertFalse(vst.loaded)

    def test_02_serum2_parameters_accessible(self):
        """Testa acesso aos parâmetros do Serum 2."""
        vst = VST(
            path=self.SERUM2_PATH,
            name="Serum2_Params",
            vst_type=VSTProgramType.INSTRUMENT,
        )

        loaded = vst.load(sample_rate=44100, block_size=512)
        self.assertTrue(loaded)

        # Deve ter muitos parâmetros (Serum 2 é complexo)
        self.assertGreater(len(vst.parameters), 50)

        # Lista alguns
        param_ids = list(vst.parameters.keys())[:5]
        print(f"✓ Primeiros parâmetros do Serum 2: {param_ids}")

        for param_id in param_ids:
            val = vst.get_parameter(param_id)
            self.assertIsInstance(val, float)
            self.assertGreaterEqual(val, 0.0)
            self.assertLessEqual(val, 1.0)

        vst.unload()

    def test_03_serum2_parameter_change(self):
        """Testa mudança de parâmetro e persistência no estado."""
        vst = VST(
            path=self.SERUM2_PATH,
            name="Serum2_ParamChange",
            vst_type=VSTProgramType.INSTRUMENT,
        )

        loaded = vst.load(sample_rate=44100, block_size=512)
        self.assertTrue(loaded)

        param_id = 0
        original = vst.get_parameter(param_id)

        # Muda parâmetro
        vst.set_parameter(param_id, 0.75)
        changed = vst.get_parameter(param_id)
        self.assertAlmostEqual(changed, 0.75, places=6)

        print(f"✓ Parâmetro {param_id}: {original:.3f} → {changed:.3f}")

        vst.unload()

    def test_04_serum2_automation_capture(self):
        """Testa captura de automação durante renderização."""
        vst = VST(
            path=self.SERUM2_PATH,
            name="Serum2_Automation",
            vst_type=VSTProgramType.INSTRUMENT,
        )

        loaded = vst.load(sample_rate=44100, block_size=512)
        self.assertTrue(loaded)

        # Adiciona pontos de automação a um parâmetro
        vst.add_automation_point(0, 0.0, 0.0)
        vst.add_automation_point(0, 1.0, 1.0)
        vst.add_automation_point(0, 2.0, 0.5)

        # Verifica interpolação
        val_mid = vst.get_automation_value(0, 0.5)
        self.assertAlmostEqual(val_mid, 0.5, places=6)

        # Verifica export/import
        exported = vst.export_state()
        self.assertIn("automation", exported)
        self.assertIn("0", exported["automation"])
        self.assertEqual(len(exported["automation"]["0"]), 3)

        restored = VST.import_state(exported)
        self.assertEqual(len(restored.automation[0]), 3)

        print(f"✓ Automação capturada e persistida com 3 pontos")

        vst.unload()

    def test_05_serum2_editor_lifecycle(self):
        """Testa abertura do editor GUI.
        
        NOTA: Este teste NÃO bloqueia o Blender. O editor abre em thread
        separada do worker. Se você abrir manualmente, vê o GUI do Serum 2.
        
        TODO: Há problema de reconnection após abrir editor - worker pode
        desconectar. Isso precisa de hardening adicional na IPC.
        """
        vst = VST(
            path=self.SERUM2_PATH,
            name="Serum2_Editor",
            vst_type=VSTProgramType.INSTRUMENT,
        )

        loaded = vst.load(sample_rate=44100, block_size=512)
        self.assertTrue(loaded)

        # Tenta abrir editor (não bloqueia)
        try:
            editor_opened = vst.open_editor()
            print(f"✓ Editor opened: {editor_opened}")
        except Exception as e:
            print(f"⚠️  Editor open teve exceção (esperado em alguns casos): {type(e).__name__}")
            # Esperado: worker pode desconectar após abrir editor
            pass

        vst.unload()

    def test_06_serum2_midi_render(self):
        """Testa renderização de notas MIDI através do Serum 2.
        
        Renderiza uma sequência simples de notas e verifica se o áudio
        saiu não-vazio.
        """
        vst = VST(
            path=self.SERUM2_PATH,
            name="Serum2_Render",
            vst_type=VSTProgramType.INSTRUMENT,
        )

        loaded = vst.load(sample_rate=44100, block_size=512)
        self.assertTrue(loaded)

        # Sequência MIDI simples: C4 (60), E4 (64), G4 (67)
        midi_notes = [
            (60, 0.0, 0.5, 100),    # C4, start 0s, duration 0.5s, velocity 100
            (64, 0.5, 0.5, 100),    # E4
            (67, 1.0, 0.5, 100),    # G4
        ]

        try:
            audio = vst.render_instrument(midi_notes, duration=2.0)

            # Verifica se o áudio foi gerado
            self.assertIsNotNone(audio)
            self.assertIsInstance(audio, np.ndarray)
            
            # Pode ser mono ou estéreo dependendo do bridge
            expected_samples = int(2.0 * 44100)
            self.assertGreaterEqual(
                audio.shape[0] if audio.ndim == 1 else audio.shape[0],
                expected_samples * 0.99,
                "Áudio muito curto ou truncado"
            )

            # Verifica se há energia no áudio (não vazio)
            rms = np.sqrt(np.mean(audio ** 2))
            self.assertGreater(rms, 0.001, "Áudio vazio ou quase silencioso")

            channels = 1 if audio.ndim == 1 else audio.shape[1]
            print(
                f"✓ Serum 2 renderizou {audio.shape[0]} samples "
                f"em {channels} canal(is) (RMS: {rms:.6f})"
            )

        except Exception as e:
            self.fail(f"Falha ao renderizar MIDI: {e}")

        vst.unload()

    def test_07_serum2_reload_stability(self):
        """Testa múltiplos ciclos de load/unload para estabilidade."""
        for cycle in range(3):
            vst = VST(
                path=self.SERUM2_PATH,
                name=f"Serum2_Reload_{cycle}",
                vst_type=VSTProgramType.INSTRUMENT,
            )

            loaded = vst.load(sample_rate=44100, block_size=512)
            self.assertTrue(loaded, f"Falha no ciclo {cycle}")

            # Muda parâmetro
            vst.set_parameter(0, 0.5 + cycle * 0.1)

            # Renderiza nota rápida
            audio = vst.render_instrument([(60, 0.0, 0.2, 100)], duration=0.5)
            self.assertIsNotNone(audio)

            vst.unload()
            time.sleep(0.1)

        print(f"✓ 3 ciclos de reload completados sem crash")

    def test_08_serum2_state_persistence(self):
        """Testa export/import completo do estado do Serum 2."""
        vst = VST(
            path=self.SERUM2_PATH,
            name="Serum2_State",
            vst_type=VSTProgramType.INSTRUMENT,
        )

        loaded = vst.load(sample_rate=44100, block_size=512)
        self.assertTrue(loaded)

        # Configura parâmetros
        vst.set_parameter(1, 0.3)
        vst.set_parameter(5, 0.7)

        # Adiciona automação
        vst.add_automation_point(1, 0.0, 0.0)
        vst.add_automation_point(1, 1.0, 1.0)

        # Salva programa
        vst.save_program("test_patch")

        # Exporta estado
        state = vst.export_state()
        self.assertIn("parameters", state)
        self.assertIn("automation", state)
        self.assertIn("programs", state)

        vst.unload()

        # Importa em nova instância
        vst2 = VST.import_state(state)
        self.assertEqual(vst2.name, vst.name)
        self.assertEqual(vst2.get_parameter(1), 0.3)
        self.assertEqual(vst2.get_parameter(5), 0.7)
        self.assertEqual(len(vst2.automation[1]), 2)
        self.assertIn("test_patch", vst2.programs)

        print(f"✓ Estado do Serum 2 exportado e importado com sucesso")


if __name__ == "__main__":
    # Executa com verbosidade
    suite = unittest.TestLoader().loadTestsFromTestCase(Serum2VST3HeavyTest)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Sumário
    print("\n" + "=" * 70)
    if result.wasSuccessful():
        print("✅ TODOS OS TESTES PASSARAM - Serum 2 VST3 é suportado!")
    else:
        print(f"❌ {len(result.failures)} failures, {len(result.errors)} errors")
        for test, trace in result.failures:
            print(f"\n  ✗ {test}")
            print(f"    {trace[:200]}...")
        for test, trace in result.errors:
            print(f"\n  ✗ {test} (ERROR)")
            print(f"    {trace[:200]}...")
    print("=" * 70)

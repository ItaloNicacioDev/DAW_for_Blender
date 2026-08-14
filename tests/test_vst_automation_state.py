import unittest

from daw.modules.vst.vst import VST, VSTAutomationPoint, VSTProgramType


class VSTAutomationStateTests(unittest.TestCase):
    def test_export_import_state_keeps_automation_points(self):
        vst = VST(
            path="C:/Plugins/TestSynth.vst3",
            name="TestSynth",
            vst_type=VSTProgramType.INSTRUMENT,
            vst_id="testsynth",
        )

        vst.set_parameter(0, 0.25)
        vst.add_automation_point(0, 0.0, 0.1)
        vst.add_automation_point(0, 1.0, 0.8)
        vst.add_automation_point(1, 0.5, 0.5)

        exported = vst.export_state()
        restored = VST.import_state(exported)

        self.assertEqual(restored.parameters[0], 0.25)
        self.assertEqual(restored.automation[0][0].value, 0.1)
        self.assertEqual(restored.automation[0][1].time, 1.0)
        self.assertEqual(restored.automation[1][0].value, 0.5)

    def test_automation_points_are_sorted_by_time(self):
        vst = VST(path="C:/Plugins/TestFx.vst3", name="TestFx")

        vst.add_automation_point(4, 2.0, 0.9)
        vst.add_automation_point(4, 0.5, 0.2)
        vst.add_automation_point(4, 1.0, 0.6)

        times = [event.time for event in vst.automation[4]]
        self.assertEqual(times, [0.5, 1.0, 2.0])


if __name__ == "__main__":
    unittest.main()

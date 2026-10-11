"""DubStage stage helpers on a hidden window: caption fitting, own-line steps."""

import gc
import runpy
import os
import sys
import tkinter as tk
import types
import unittest
from unittest.mock import patch


@unittest.skipUnless(sys.platform == "win32" or os.environ.get("DISPLAY"), "Tk display required")
class StageHelperTests(unittest.TestCase):
    def setUp(self):
        # Tk-Objekte hier auf dem Hauptthread freigeben (siehe test_caption_ui)
        self.addCleanup(self._release_tk)
        namespace = runpy.run_path("DubStage.pyw", run_name="ui_test")
        self.Game = namespace["Game"]
        globals_ = self.Game.__init__.__globals__
        original_init = tk.Tk.__init__

        def hidden_init(root, *args, **kwargs):
            original_init(root, *args, **kwargs)
            root.withdraw()

        for context in (
                patch.object(tk.Tk, "__init__", hidden_init),
                patch.dict(globals_, {"load_cfg": lambda: {"lang": "en"},
                                      "save_cfg": lambda cfg: None}),
                patch.object(self.Game, "_check_update"),
                patch.object(self.Game, "show_menu")):
            context.start()
            self.addCleanup(context.stop)
        self.game = self.Game()
        self.addCleanup(self.game.destroy)

    def _release_tk(self):
        self.game = self.Game = None
        gc.collect()

    def caption(self, text, max_h=46):
        cv = self.game.cv
        item = cv.create_text(300, 10, anchor="n", text="", width=560,
                              font=("Segoe UI Semibold", 16))
        self.game._fit_text(item, text, max_h)
        x0, y0, x1, y1 = cv.bbox(item)
        return item, y1 - y0, cv.itemcget(item, "text"), cv.itemcget(item, "font")

    def test_short_caption_keeps_size(self):
        _item, h, text, font = self.caption("I am Groot")
        self.assertLessEqual(h, 46)
        self.assertEqual(text, "I am Groot")
        self.assertIn("16", font)

    def test_long_caption_shrinks_into_its_box(self):
        long = " ".join(["word"] * 24)
        _item, h, text, font = self.caption(long)
        self.assertLessEqual(h, 46)
        self.assertEqual(text, long)
        self.assertNotIn("16", font)

    def test_huge_caption_is_cut_with_ellipsis(self):
        _item, h, text, _font = self.caption(" ".join(["word"] * 400))
        self.assertLessEqual(h, 46)
        self.assertTrue(text.endswith("…"))

    def test_own_step_skips_other_players_lines(self):
        owners = ["b", "a", "b", "b", "a", "b"]
        lines = [types.SimpleNamespace(file="l%d" % i) for i in range(6)]
        self.game.pack = types.SimpleNamespace(lines=lines)
        self.game.net = types.SimpleNamespace(
            me="a", state={"owner": {l.file: o for l, o in zip(lines, owners)}})
        self.game.line_i = 1
        self.assertEqual(self.game._own_step(1), 4)
        self.assertIsNone(self.game._own_step(-1))
        self.game.line_i = 4
        self.assertIsNone(self.game._own_step(1))
        self.assertEqual(self.game._own_step(-1), 1)
        self.game.line_i = 0        # fremde Zeile, per Leiste angesprungen
        self.assertEqual(self.game._own_step(1), 1)
        self.game.net = None


if __name__ == "__main__":
    unittest.main()

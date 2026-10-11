"""Choicer-Voicer-Packs in DubStage: .txt-Metadaten lesen und Pack laden."""

import io
import os
import shutil
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dubforge_core as pc
import dubstage_core as ds
import dubstage_net as net

# So schreibt das Spiel selbst - mehrzeiliger Untertitel inklusive.
REAL_META = ('[data]\r\n\r\ncaption="[Verbalase] “Hey whats up guys.\r\n\r\n'
             ' ”"\r\nimage="01_Verbalase.png"\r\ndub_timestamps=[0.260]\r\n'
             'dub_characters=["Verbalase"]')


def write(path, text):
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


class ParseTests(unittest.TestCase):
    def test_parses_real_meta_with_multiline_caption(self):
        d = pc.parse_cv(REAL_META)
        self.assertEqual(d["dub_timestamps"], [0.26])
        self.assertEqual(d["dub_characters"], ["Verbalase"])
        self.assertEqual(d["image"], "01_Verbalase.png")
        self.assertEqual(pc.cv_caption_text(d["caption"]),
                         "Hey whats up guys.")

    def test_roundtrip_with_writer(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        path = os.path.join(root, "01_buzz.txt")
        pc.write_cv_meta(path, caption='[Buzz] "To infinity"',
                         image="buzz.png", timestamps=[1.5, 12.25],
                         characters=["Buzz"])
        d = pc.read_cv_file(path)
        self.assertEqual(d["dub_timestamps"], [1.5, 12.25])
        self.assertEqual(d["dub_characters"], ["Buzz"])
        self.assertEqual(pc.cv_caption_text(d["caption"]), "To infinity")

    def test_pack_info(self):
        d = pc.parse_cv('[data]\r\n\r\ntitle="Pennywise vs Groot"\r\n'
                        'icon="icon.png"\r\nauthors=["A","B"]\r\nreadme=""')
        self.assertEqual(d["title"], "Pennywise vs Groot")
        self.assertEqual(d["authors"], ["A", "B"])
        self.assertEqual(d["readme"], "")


class LoadPackTests(unittest.TestCase):
    def setUp(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        self.folder = os.path.join(root, "Compressed", "pennywise_vs_groot",
                                   "Pennywise vs Groot")
        os.makedirs(self.folder)
        tone = 0.2 * np.sin(np.linspace(0, 300, ds.SR // 2))
        for name, ts, who, cap in (
                ("01_Verbalase", "[0.260]", "Verbalase", "Hello"),
                ("301_Groot", "[20.000,05.500]", "Groot", "i am groot"),
                ("201_Patrick star", "[10.000]", "Patrick star", "Yay")):
            ds.write_wav_mono(os.path.join(self.folder, name + ".wav"), tone)
            write(os.path.join(self.folder, name + ".txt"),
                  '[data]\r\n\r\ncaption="[%s] “%s”"\r\n'
                  'image="%s.png"\r\ndub_timestamps=%s\r\n'
                  'dub_characters=["%s"]' % (who, cap, name, ts, who))
        ds.write_wav_mono(os.path.join(self.folder, "_backing_track.wav"),
                          tone)
        write(os.path.join(self.folder, "dub_video.ogv"), "x")
        write(os.path.join(self.folder, "_pack_info.ini"),
              '[data]\r\n\r\ntitle="Pennywise vs Groot"\r\nicon="icon.png"')

    def test_loads_lines_in_scene_order(self):
        pack = ds.load_pack(self.folder)
        self.assertIsNotNone(pack)
        self.assertEqual(pack.name, "Pennywise vs Groot")
        self.assertTrue(pack.backing.endswith("_backing_track.wav"))
        self.assertEqual([(l.start, l.name) for l in pack.lines],
                         [(0.26, "Verbalase"), (5.5, "Groot"),
                          (10.0, "Patrick star"), (20.0, "Groot")])
        self.assertEqual([l.caption for l in pack.lines],
                         ["Hello", "i am groot", "Yay", "i am groot"])

    def test_clip_used_twice_gets_unique_keys(self):
        pack = ds.load_pack(self.folder)
        groot = [l for l in pack.lines if l.name == "Groot"]
        self.assertEqual([l.file for l in groot],
                         ["301_Groot.wav", "301_Groot.wav#2"])
        self.assertEqual(groot[0].path, groot[1].path)

    def test_find_packs_in_zip_wrapper_and_pack_itself(self):
        # Compressed/<zip name>/<pack>: der Pack liegt zwei Ebenen tief
        downloads = os.path.dirname(os.path.dirname(self.folder))
        wrapper = os.path.dirname(self.folder)
        for root in (downloads, wrapper, self.folder):
            self.assertEqual([p.name for p in ds.find_packs([root])],
                             ["Pennywise vs Groot"], root)
        both = ds.find_packs([downloads, self.folder])
        self.assertEqual(len(both), 1)

    def test_multiplayer_accepts_cv_lines(self):
        pack = ds.load_pack(self.folder)
        room = net.Room(pack)
        server = net.Server(room, port=0, host="127.0.0.1")
        self.addCleanup(server.close)
        room.join("Host", host=True)
        c = net.Client("127.0.0.1:%d" % server.port, room.code)
        c.join("Gast")
        key = "301_Groot.wav#2"
        room.assign(key, c.player)
        c.upload_take(key, np.zeros(1000, np.float32))
        self.assertIn(key, c.state()["takes"])
        self.assertEqual(len(c.fetch_take(key)), 1000)


if __name__ == "__main__":
    unittest.main()

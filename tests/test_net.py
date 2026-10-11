"""Tests fuer den Mehrspieler-Teil: Raum, Server, Client, Pack-Transfer."""

import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import zipfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dubstage_core as ds
import dubstage_net as net


def make_pack(root, name="Testpack"):
    folder = os.path.join(root, name)
    os.makedirs(folder)
    sr = ds.SR
    for i, (who, start) in enumerate((("Anna", "1-000"), ("Ben", "3-500"),
                                      ("Anna", "6-250"))):
        tone = 0.3 * np.sin(np.linspace(0, 200 * (i + 1), sr // 2))
        ds.write_wav_mono(os.path.join(folder, "%02d_%s_%s.wav"
                                       % (i + 1, who, start)), tone, sr)
    with open(os.path.join(folder, "dub_video.mp4"), "wb") as f:
        f.write(os.urandom(4096))
    with open(os.path.join(folder, "_captions.json"), "w",
              encoding="utf-8") as f:
        f.write('{"01_Anna_1-000.wav": "Hallo"}')
    return ds.load_pack(folder)


class HelperTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_normalize_address(self):
        n = net.normalize_address
        self.assertEqual(n("1.2.3.4"), "http://1.2.3.4:%d" % net.DEFAULT_PORT)
        self.assertEqual(n(" 1.2.3.4:9000/ "), "http://1.2.3.4:9000")
        self.assertEqual(n("abc-def.trycloudflare.com"),
                         "https://abc-def.trycloudflare.com")
        self.assertEqual(n("https://abc.trycloudflare.com/x"),
                         "https://abc.trycloudflare.com")
        with self.assertRaises(net.NetError):
            n("")

    def test_wav_roundtrip(self):
        data = (0.5 * np.sin(np.linspace(0, 50, 4410))).astype(np.float32)
        back = net.wav_from_bytes(net.wav_bytes(data))
        self.assertEqual(len(back), len(data))
        self.assertLess(float(np.max(np.abs(back - data))), 1e-3)

    def test_safe_extract_rejects_traversal(self):
        bad = os.path.join(self.root, "bad.zip")
        with zipfile.ZipFile(bad, "w") as z:
            z.writestr("../evil.txt", "x")
        with self.assertRaises(net.NetError):
            net.safe_extract(bad, os.path.join(self.root, "out"))
        self.assertFalse(os.path.exists(os.path.join(self.root, "evil.txt")))

    def test_auto_assign_keeps_characters_together(self):
        pack = make_pack(self.root)
        for l in pack.lines:
            l.duration = 1.0
        out = net.auto_assign(pack.lines, ["p1", "p2"])
        anna = [out[l.file] for l in pack.lines if l.name == "Anna"]
        ben = [out[l.file] for l in pack.lines if l.name == "Ben"]
        self.assertEqual(len(set(anna)), 1)
        self.assertNotEqual(anna[0], ben[0])

    def test_auto_assign_splits_lines_when_few_characters(self):
        pack = make_pack(self.root)
        out = net.auto_assign(pack.lines, ["p1", "p2", "p3"])
        self.assertEqual(sorted(set(out.values())), ["p1", "p2", "p3"])


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.pack = make_pack(self.root)
        self.room = net.Room(self.pack)
        self.server = net.Server(self.room, port=0, host="127.0.0.1")
        self.addCleanup(self.server.close)
        self.addr = "127.0.0.1:%d" % self.server.port
        self.room.join("Host", host=True)
        # Heruntergeladene Packs in einen Testordner umleiten
        self._old_net_dir = net.NET_DIR
        net.NET_DIR = os.path.join(self.root, "net")
        self.addCleanup(setattr, net, "NET_DIR", self._old_net_dir)

    def client(self, name):
        c = net.Client(self.addr, self.room.code.lower())
        c.join(name)
        self.addCleanup(c.stop_polling)
        return c

    def test_wrong_room_code_is_rejected(self):
        c = net.Client(self.addr, "WRONG1")
        with self.assertRaises(net.NetError) as cm:
            c.join("Eve")
        self.assertIn("room code", str(cm.exception))

    def test_take_flows_between_players(self):
        a, b = self.client("Anna"), self.client("Anna")
        st = b.state()
        names = sorted(p["name"] for p in st["players"])
        self.assertEqual(names, ["Anna", "Anna 2", "Host"])

        line = self.pack.lines[1].file
        self.room.assign(line, a.player)
        data = (0.4 * np.sin(np.linspace(0, 99, 8000))).astype(np.float32)
        a.upload_take(line, data)
        st = b.state()
        self.assertEqual(st["takes"][line]["player"], a.player)
        got = b.fetch_take(line)
        self.assertLess(float(np.max(np.abs(got - data))), 1e-3)

        # Fremde Zeilen darf niemand ueberschreiben
        with self.assertRaises(net.NetError):
            b.upload_take(line, data)
        with self.assertRaises(net.NetError):
            b.delete_take(line)
        a.delete_take(line)
        self.assertNotIn(line, b.state()["takes"])

    def test_unknown_line_is_rejected(self):
        a = self.client("Anna")
        with self.assertRaises(net.NetError):
            a.upload_take("../../evil.wav", np.zeros(100, np.float32))

    def test_pack_download_matches_hash(self):
        a = self.client("Anna")
        seen = []
        folder = a.download_pack(a.state(), seen.append)
        self.assertEqual(net.pack_hash(folder), self.room.pack_hash)
        self.assertEqual(seen[-1], 1.0)
        copy = ds.load_pack(folder)
        self.assertEqual([l.file for l in copy.lines],
                         [l.file for l in self.pack.lines])
        self.assertEqual(copy.lines[0].caption, "Hallo")
        # Zweites Mal: schon vorhanden, kein neuer Download
        self.assertEqual(a.download_pack(a.state()), folder)

    def test_long_poll_wakes_up_on_change(self):
        a = self.client("Anna")
        v = a.state()["version"]
        threading.Timer(0.3, self.room.start).start()
        t0 = time.time()
        st = a.state(v)
        self.assertLess(time.time() - t0, 5.0)
        self.assertEqual(st["phase"], "recording")

    def test_guests_learn_when_host_closes(self):
        a = self.client("Anna")
        v = a.state()["version"]
        threading.Timer(0.2, self.server.close).start()
        self.assertEqual(a.state(v)["phase"], "closed")

    def test_polling_thread_and_leave(self):
        a = self.client("Anna")
        events = []
        got = threading.Event()

        def sink(kind, payload):
            events.append((kind, payload))
            if kind == "net" and payload["phase"] == "recording":
                got.set()

        a.start_polling(sink)
        self.room.assign_all({l.file: a.player for l in self.pack.lines})
        self.room.start()
        self.assertTrue(got.wait(5.0))
        a.leave()
        st = self.room.snapshot()
        me = [p for p in st["players"] if p["id"] == a.player][0]
        self.assertTrue(me["left"])
        # Zeilen fallen an den Host zurueck
        self.assertEqual(set(st["owner"].values()), {self.room.host_id})


if __name__ == "__main__":
    unittest.main()

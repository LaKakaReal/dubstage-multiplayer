"""Hintergrund getrennt mischen: gleiches Ergebnis wie vorher, Regler wirkt live."""

import os
import shutil
import sys
import tempfile
import types
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dubstage_core as ds

SR = ds.SR


def old_render_dub(pack, sr=SR, duck=0.18):
    """render_dub vor der Aufteilung - Referenz fuer den Vergleich."""
    total = max(pack.video_duration, 0.1)
    for line in pack.lines:
        total = max(total, line.end + 1.0)
    n = int(total * sr) + sr
    base = np.zeros(n, dtype=np.float32)
    backing = pack.backing_audio
    if backing is not None:
        base[:min(n, len(backing))] = backing[:n]
    else:
        original = ds.read_wav_mono(pack.video, sr)
        base[:min(n, len(original))] = original[:n]
    for line in pack.lines:
        a = int(line.start * sr)
        if line.take is not None and len(line.take):
            take = ds.normalize(np.asarray(line.take, dtype=np.float32), 0.92)
            if backing is None:
                b = min(n, a + max(len(take), int(line.duration * sr)))
                base[a:b] *= duck
            b = min(n, a + len(take))
            base[a:b] += take[:b - a]
        elif line.audio is not None and backing is not None:
            b = min(n, a + len(line.audio))
            base[a:b] += line.audio[:b - a] * 0.9
    return ds.normalize(base, 0.97)


def tone(freq, seconds, amp=0.3):
    t = np.arange(int(seconds * SR)) / float(SR)
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def line(start, dur, take=None):
    return types.SimpleNamespace(start=start, duration=dur, end=start + dur,
                                 audio=tone(300, dur), take=take)


class RenderPartsTests(unittest.TestCase):
    def pack(self, backing=True):
        lines = [line(0.5, 1.0, take=tone(500, 1.2, 0.5)), line(2.0, 0.8),
                 line(3.5, 1.0, take=tone(700, 0.6, 0.1))]
        p = types.SimpleNamespace(lines=lines, video_duration=5.0,
                                  backing_audio=tone(110, 5.0, 0.4) if backing
                                  else None, video=None)
        if not backing:
            root = tempfile.mkdtemp()
            self.addCleanup(shutil.rmtree, root, True)
            p.video = ds.write_wav_mono(os.path.join(root, "video.wav"),
                                        tone(150, 5.0, 0.6), SR)
        return p

    def test_render_dub_is_unchanged(self):
        for backing in (True, False):
            p = self.pack(backing)
            np.testing.assert_allclose(ds.render_dub(p), old_render_dub(p),
                                       atol=1e-5, err_msg="backing=%s" % backing)

    def test_mix_parts_share_one_scale(self):
        voices, back = ds.render_dub_parts(self.pack())
        v, b = ds.mix_parts(voices, back)
        self.assertAlmostEqual(float(np.max(np.abs(v + b))), 0.97, places=4)
        k = float(np.max(np.abs(v))) / float(np.max(np.abs(voices)))
        np.testing.assert_allclose(b, back * k, atol=1e-5)


class PlayMixTests(unittest.TestCase):
    def setUp(self):
        streams = []

        class Stop(Exception):
            pass

        class OutputStream(object):
            def __init__(self, callback, **kw):
                self.callback = callback
                streams.append(self)

            def start(self):
                pass

            def stop(self):
                pass

            def close(self):
                pass

        self.streams = streams
        self.mic = ds.Mic()
        self.mic.sd = types.SimpleNamespace(OutputStream=OutputStream,
                                            CallbackStop=Stop,
                                            stop=lambda: None)

    def test_background_follows_gain_live(self):
        voices = np.full(8, 0.1, dtype=np.float32)
        back = np.full(8, 0.2, dtype=np.float32)
        self.mic.play_mix(voices, back)
        cb = self.streams[-1].callback
        out = np.zeros((4, 1), dtype=np.float32)
        cb(out, 4, None, None)
        np.testing.assert_allclose(out[:, 0], 0.3, atol=1e-6)
        self.mic.back_gain = 0.0                  # mitten im Abspielen
        with self.assertRaises(self.mic.sd.CallbackStop):
            cb(out, 4, None, None)
        np.testing.assert_allclose(out[:, 0], 0.1, atol=1e-6)

    def test_end_pads_silence_and_clips(self):
        self.mic.back_gain = 1.5
        self.mic.play_mix(np.full(3, 0.5, dtype=np.float32),
                          np.full(3, 0.5, dtype=np.float32))
        out = np.ones((5, 1), dtype=np.float32)
        with self.assertRaises(self.mic.sd.CallbackStop):
            self.streams[-1].callback(out, 5, None, None)
        np.testing.assert_allclose(out[:, 0], [1, 1, 1, 0, 0])

    def test_background_only_while_recording(self):
        self.mic.play_mix(None, np.full(4, 0.4, dtype=np.float32))
        self.mic.back_gain = 0.5
        out = np.zeros((4, 1), dtype=np.float32)
        with self.assertRaises(self.mic.sd.CallbackStop):
            self.streams[-1].callback(out, 4, None, None)
        np.testing.assert_allclose(out[:, 0], 0.2, atol=1e-6)


if __name__ == "__main__":
    unittest.main()

"""Packs als Zip oder RAR: erkennen, entpacken, fremde Archive in Ruhe lassen."""

import os
import shutil
import sys
import tempfile
import unittest
import zipfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
import dubstage_core as ds
from rar4 import write_rar4


def pack_files(prefix="Szene/"):
    tone = (0.3 * np.sin(np.linspace(0, 200, ds.SR // 2))).astype(np.float32)
    tmp = tempfile.mkdtemp()
    try:
        with open(ds.write_wav_mono(os.path.join(tmp, "a.wav"), tone), "rb") as f:
            wav = f.read()
    finally:
        shutil.rmtree(tmp, True)
    return {prefix + "01_Anna_1-000.wav": wav, prefix + "02_Ben_3-500.wav": wav,
            prefix + "dub_video.mp4": os.urandom(2048)}


def write_zip(path, files):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return path


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.downloads = os.path.join(self.root, "downloads")
        os.makedirs(self.downloads)
        for attr, sub in (("PACKS_DIR", "packs"), ("ARCHIVES_DIR", "packs/_archives")):
            self.addCleanup(setattr, ds, attr, getattr(ds, attr))
            setattr(ds, attr, os.path.join(self.root, sub))
        os.makedirs(ds.PACKS_DIR)
        self.addCleanup(ds.NOT_PACKS.clear)

    def scan(self, extra):
        pending = []
        packs = ds.find_packs(extra, pending)
        return [p.name for p in packs], pending

    def unpack_all(self, pending):
        for p in pending:
            if ds.archive_has_pack(p):
                ds.extract_archive(p)
            else:
                ds.NOT_PACKS.add(ds.archive_target(p))

    def test_zip_in_folder_is_found_after_unpacking(self):
        z = write_zip(os.path.join(self.downloads, "szene.zip"), pack_files())
        names, pending = self.scan([self.downloads])
        self.assertEqual((names, pending), ([], [z]))
        self.unpack_all(pending)
        names, pending = self.scan([self.downloads])
        self.assertEqual((names, pending), (["Szene"], []))
        self.assertTrue(ds.archive_target(z).startswith(ds.ARCHIVES_DIR))

    def test_zip_in_packs_folder_and_flat_zip(self):
        write_zip(os.path.join(ds.PACKS_DIR, "flach.zip"), pack_files(prefix=""))
        _names, pending = self.scan([])
        self.unpack_all(pending)
        names, _ = self.scan([])
        self.assertEqual(len(names), 1)

    @unittest.skipUnless(ds._rar_tools(), "no program that reads RAR")
    def test_rar_added_directly(self):
        rar = write_rar4(os.path.join(self.root, "szene.rar"), pack_files())
        self.assertTrue(ds.archive_has_pack(rar))
        _names, pending = self.scan([rar])
        self.assertEqual(pending, [rar])
        self.unpack_all(pending)
        names, pending = self.scan([rar])
        self.assertEqual((names, pending), (["Szene"], []))

    def test_other_archives_are_left_alone(self):
        z = write_zip(os.path.join(self.downloads, "shader.zip"),
                      {"shaders/a.glsl": b"void main(){}"})
        self.assertFalse(ds.archive_has_pack(z))
        _names, pending = self.scan([self.downloads])
        self.unpack_all(pending)
        names, pending = self.scan([self.downloads])
        self.assertEqual((names, pending), ([], []))
        self.assertFalse(os.path.isdir(ds.archive_target(z)))

    def test_zip_next_to_its_unpacked_folder_is_skipped(self):
        z = write_zip(os.path.join(self.downloads, "szene.zip"), pack_files())
        with zipfile.ZipFile(z) as f:
            f.extractall(os.path.join(self.downloads, "szene"))
        names, pending = self.scan([self.downloads])
        self.assertEqual((names, pending), (["Szene"], []))

    def test_unsafe_zip_paths_are_refused(self):
        z = write_zip(os.path.join(self.root, "evil.zip"),
                      {"dub_video.mp4": b"x", "../../evil.txt": b"x"})
        with self.assertRaises(RuntimeError):
            ds.extract_archive(z)
        self.assertFalse(os.path.exists(os.path.join(self.root, "evil.txt")))
        self.assertFalse(os.path.exists(ds.archive_target(z)))
        self.assertFalse(os.path.exists(ds.archive_target(z) + ".part"))

    def test_replaced_archive_gets_a_new_folder(self):
        z = write_zip(os.path.join(self.root, "szene.zip"), pack_files())
        first = ds.archive_target(z)
        write_zip(z, pack_files(prefix="Neu/"))
        os.utime(z, (1, 1))
        self.assertNotEqual(ds.archive_target(z), first)


if __name__ == "__main__":
    unittest.main()

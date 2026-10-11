# -*- coding: utf-8 -*-
"""
dubstage_core.py  --  Spiel-Logik fuer DubStage / game logic.

Video laeuft, Zeile nachsprechen, am Ende laeuft die ganze Szene
mit der eigenen Stimme. Keine GUI hier drin.
"""

import os
import re
import glob
import shutil
import struct
import tempfile
import wave

import numpy as np

import dubforge_core as pc

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PACKS_DIR = os.path.join(APP_DIR, "packs")
CACHE_DIR = os.path.join(tempfile.gettempdir(), "dubstage_cache")

SR = 44100                 # Arbeits-Samplerate / working sample rate
FRAME_FPS = 25             # Bilder pro Sekunde fuer die Wiedergabe
FRAME_W = 960              # Breite der Einzelbilder - nie hochskalieren


# ==========================================================================
#  Packs finden / find packs
# ==========================================================================

class Line(object):
    """Eine Zeile des Dub-Packs / one line of a dub pack."""

    def __init__(self, path, start, index):
        self.path = path
        self.file = os.path.basename(path)
        self.start = float(start)
        self.index = index
        self.name = self._label()
        self.caption = ""       # Untertitel / subtitle
        self.audio = None       # Original-Sample / original sample
        self.duration = 0.0
        self.take = None        # Aufnahme des Spielers / player recording

    def _label(self):
        stem = os.path.splitext(self.file)[0]
        stem = re.sub(r"^\d+[_\-]", "", stem)
        stem = re.sub(r"_\d+-\d{1,3}$", "", stem)
        return stem.replace("_", " ").strip() or self.file

    @property
    def end(self):
        return self.start + self.duration


class DubPack(object):

    def __init__(self, folder):
        self.folder = folder
        self.name = os.path.basename(folder)
        self.video = None
        self.backing = None
        self.lines = []
        self.frames = []
        self.fps = FRAME_FPS
        self.video_duration = 0.0

    def __repr__(self):
        return "<DubPack %s, %d Zeilen>" % (self.name, len(self.lines))


_TS_IN_NAME = re.compile(r"_(\d+)-(\d{1,3})(?:\.[A-Za-z0-9]+)?$")


def timestamp_from_name(filename):
    """'07_MyClip_44-048.wav' -> 44.048 ; sonst None."""
    stem = os.path.splitext(os.path.basename(filename))[0]
    m = _TS_IN_NAME.search(stem)
    if not m:
        return None
    whole, frac = m.group(1), m.group(2)
    return float(whole) + float(frac) / (10 ** len(frac))


def timestamps_from_txt(folder):
    """Liest _TIMESTAMPS.txt als Rueckfallebene / fallback."""
    path = os.path.join(folder, "_TIMESTAMPS.txt")
    out = {}
    if not os.path.isfile(path):
        return out
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                m = re.match(r"(\S+\.wav)\s+(-?[\d.]+)", line)
                if m:
                    out[m.group(1)] = float(m.group(2))
    except Exception:
        pass
    return out


AUDIO_EXT = (".wav", ".mp3", ".ogg", ".flac")
VIDEO_EXT = (".mp4", ".ogv", ".mkv", ".webm", ".mov", ".avi")


def load_pack(folder):
    """Baut ein DubPack aus einem Ordner. None, wenn kein Dub-Pack."""
    if not os.path.isdir(folder):
        return None
    video = None
    for ext in VIDEO_EXT:                       # mp4 bevorzugt, ogv weiter ok
        cand = os.path.join(folder, "dub_video" + ext)
        if os.path.isfile(cand):
            video = cand
            break
    if not video:
        return None

    pack = DubPack(folder)
    pack.video = video

    from_txt = timestamps_from_txt(folder)
    cv = {}                                     # Choicer-Voicer-Metadaten
    entries = []
    for f in sorted(os.listdir(folder)):
        low = f.lower()
        if not low.endswith(AUDIO_EXT):
            continue
        if low.startswith("_backing_track"):
            pack.backing = os.path.join(folder, f)
            continue
        if f.startswith("_"):
            continue
        ts = timestamp_from_name(f)
        if ts is None:
            ts = from_txt.get(f)
        if ts is not None:
            entries.append((f, ts, 1))
            continue
        # Choicer Voicer: Zeitstempel in der .txt neben dem Clip, ein Clip
        # darf an mehreren Stellen der Szene laufen.
        meta = _cv_meta(folder, f)
        if meta is not None:
            cv[f] = meta
            for n, t in enumerate(meta["timestamps"]):
                entries.append((f, t, n + 1))

    if not entries:
        # Ohne Zeitstempel koennen wir nicht synchronisieren.
        return None

    entries.sort(key=lambda e: e[1])
    captions = pc.read_captions(folder)
    for i, (f, ts, n) in enumerate(entries):
        line = Line(os.path.join(folder, f), ts, i)
        if n > 1:
            line.file = "%s#%d" % (f, n)     # eindeutiger Schluessel
        line.caption = captions.get(f, "")
        meta = cv.get(f)
        if meta and meta["characters"]:
            line.name = meta["characters"][0]
        pack.lines.append(line)

    info = os.path.join(folder, pc.CV_PACK_INFO)
    if os.path.isfile(info):
        try:
            title = str(pc.read_cv_file(info).get("title") or "").strip()
            if title:
                pack.name = title
        except Exception:
            pass
    return pack


def _cv_meta(folder, audio_name):
    """Liest '<clip>.txt' im Choicer-Voicer-Format, sonst None."""
    path = os.path.join(folder, os.path.splitext(audio_name)[0] + ".txt")
    if not os.path.isfile(path):
        return None
    try:
        data = pc.read_cv_file(path)
    except Exception:
        return None
    times = data.get("dub_timestamps")
    if not isinstance(times, list):
        return None
    times = sorted(float(t) for t in times if isinstance(t, float) and t >= 0)
    if not times:
        return None
    chars = data.get("dub_characters")
    chars = [str(c).strip() for c in chars if str(c).strip()] \
        if isinstance(chars, list) else []
    return {"timestamps": times, "characters": chars}


def find_packs(extra_dirs=None, pending=None):
    """
    Sucht Dub-Packs im eigenen packs-Ordner und in zusaetzlichen Ordnern.
    Zips und RARs (dort oder direkt hinzugefuegt) zaehlen, sobald sie
    entpackt sind; noch nicht entpackte landen in der Liste pending.
    """
    roots = []

    def add_root(p):
        ok = p and (os.path.isdir(p) or (is_archive(p) and os.path.isfile(p)))
        if ok and os.path.normpath(p) not in \
                [os.path.normpath(r) for r in roots]:
            roots.append(p)

    add_root(PACKS_DIR)
    for p in (extra_dirs or []):
        add_root(p)

    packs = []
    seen = set()

    def visit(folder, depth):
        """Pack selbst, sonst eine Ebene tiefer - entpackte Zips liegen oft
        in einem Huellordner (pennywise_vs_groot/Pennywise vs Groot)."""
        key = os.path.normpath(folder).lower()
        if key in seen:
            return
        seen.add(key)
        p = load_pack(folder)
        if p:
            packs.append(p)
            return
        if depth <= 0:
            return
        try:
            entries = sorted(os.listdir(folder))
        except OSError:
            return
        for entry in entries:
            sub = os.path.join(folder, entry)
            # _net & Co. sind interne Ordner, kein Inhalt fuers Menue
            if not entry.startswith(("_", ".")) and os.path.isdir(sub):
                visit(sub, depth - 1)

    def visit_archive(path):
        """Schon entpackt: wie ein Ordner. Sonst fuer spaeter vormerken."""
        target = archive_target(path)
        if os.path.isdir(target):
            visit(target, 2)
        elif pending is not None and path not in pending                 and target not in NOT_PACKS:
            pending.append(path)

    for root in roots:
        if is_archive(root):
            visit_archive(root)
            continue
        visit(root, 2)
        # Zips und RARs direkt im Ordner (dort landen Downloads)
        try:
            entries = sorted(os.listdir(root))
        except OSError:
            entries = []
        for entry in entries:
            sub = os.path.join(root, entry)
            # Schon von Hand entpackt (X.zip neben Ordner X)? Dann den Ordner.
            if is_archive(sub) and os.path.isfile(sub)                     and not os.path.isdir(os.path.splitext(sub)[0]):
                visit_archive(sub)
    return packs


# ==========================================================================
#  Archive / zip and rar packs
# ==========================================================================

ARCHIVE_EXTS = (".zip", ".rar")
ARCHIVES_DIR = os.path.join(PACKS_DIR, "_archives")   # entpackte Archive
NOT_PACKS = set()      # Archive ohne dub_video (archive_target), je Sitzung


def is_archive(path):
    return os.path.splitext(path)[1].lower() in ARCHIVE_EXTS


def archive_target(path):
    """
    Ordner, in den ein Archiv entpackt wird. Name, Groesse und Zeitstempel
    stecken im Namen - ein ersetztes Archiv wird neu entpackt.
    """
    import hashlib
    try:
        st = os.stat(path)
        sig = "%s|%d|%d" % (os.path.normcase(os.path.abspath(path)),
                            st.st_size, int(st.st_mtime))
    except OSError:
        sig = os.path.normcase(os.path.abspath(path))
    h = hashlib.sha1(sig.encode("utf-8")).hexdigest()[:8]
    stem = pc.safe_name(os.path.splitext(os.path.basename(path))[0], "pack")
    return os.path.join(ARCHIVES_DIR, "%s-%s" % (stem[:60], h))


def _extract_zip(path, dest):
    """Entpackt ein Zip - nie ausserhalb von dest."""
    import zipfile
    root = os.path.abspath(dest)
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            name = info.filename.replace("\\", "/")
            target = os.path.abspath(os.path.join(root, *name.split("/")))
            if not target.startswith(root + os.sep):
                raise RuntimeError("Unsafe path in archive: %r" % info.filename)
            if name.endswith("/"):
                os.makedirs(target, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with z.open(info) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)


def _windows_tar():
    """Windows 10/11 bringt bsdtar (libarchive) mit, das RAR und RAR5 liest."""
    tar = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                       "System32", "tar.exe")
    return tar if os.path.isfile(tar) else None


def _rar_tools():
    """Programme, die RAR entpacken koennen - in dieser Reihenfolge."""
    tools = []
    tar = _windows_tar()
    if tar:
        tools.append(lambda src, dst: [tar, "-xf", src, "-C", dst])
    for p in (shutil.which("UnRAR"),
              os.path.join(os.environ.get("ProgramFiles", ""), "WinRAR",
                           "UnRAR.exe")):
        if p and os.path.isfile(p):
            tools.append(lambda src, dst, p=p: [p, "x", "-o+", "-y", src,
                                                dst + os.sep])
            break
    for p in (shutil.which("7z"),
              os.path.join(os.environ.get("ProgramFiles", ""), "7-Zip",
                           "7z.exe")):
        if p and os.path.isfile(p):
            tools.append(lambda src, dst, p=p: [p, "x", "-y", "-o" + dst, src])
            break
    return tools


def archive_names(path):
    """Dateinamen im Archiv, ohne zu entpacken. None = nicht lesbar."""
    try:
        if os.path.splitext(path)[1].lower() == ".zip":
            import zipfile
            with zipfile.ZipFile(path) as z:
                return z.namelist()
        tar = _windows_tar()
        if tar:
            import subprocess
            res = subprocess.run([tar, "-tf", path], capture_output=True,
                                 timeout=60, creationflags=0x08000000)
            if res.returncode != 0:
                return None
            return res.stdout.decode("utf-8", "replace").splitlines()
    except Exception:
        return None
    return None


def archive_has_pack(path):
    """
    Steckt ein Dub-Pack drin (eine dub_video-Datei)? Unbekannt zaehlt als
    ja - dann entscheidet das Entpacken.
    """
    names = archive_names(path)
    if names is None:
        return True
    for n in names:
        base = n.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1].lower()
        if base.startswith("dub_video"):
            return True
    return False


def extract_archive(path, log=None):
    """
    Entpackt ein Zip oder RAR nach archive_target(path) und gibt den Ordner
    zurueck. Erst in einen .part-Ordner, damit ein Abbruch nichts Halbes
    hinterlaesst.
    """
    target = archive_target(path)
    if os.path.isdir(target):
        return target
    part = target + ".part"
    shutil.rmtree(part, ignore_errors=True)
    os.makedirs(part)
    try:
        if os.path.splitext(path)[1].lower() == ".zip":
            _extract_zip(path, part)
        else:
            tools = _rar_tools()
            if not tools:
                raise RuntimeError("No program found that can open RAR "
                                   "files (Windows tar, WinRAR or 7-Zip).")
            err = None
            for make in tools:
                try:
                    pc.run(make(path, part), log=log)
                    err = None
                    break
                except Exception as ex:
                    err = ex
                    shutil.rmtree(part, ignore_errors=True)
                    os.makedirs(part)
            if err is not None:
                raise err
        os.replace(part, target)
    except Exception:
        shutil.rmtree(part, ignore_errors=True)
        raise
    return target


# ==========================================================================
#  Audio
# ==========================================================================

def read_wav_mono(path, sr=SR):
    """Liest beliebiges Audio als Mono-Float-Array (ueber ffmpeg)."""
    tmp = tempfile.mktemp(suffix=".wav")
    try:
        pc.run([pc.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
                "-i", path, "-ac", "1", "-ar", str(sr),
                "-c:a", "pcm_s16le", tmp], check=True)
        with wave.open(tmp, "rb") as w:
            raw = w.readframes(w.getnframes())
        return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def write_wav_mono(path, data, sr=SR):
    data = np.clip(np.asarray(data, dtype=np.float32), -1.0, 1.0)
    pcm = (data * 32767.0).astype("<i2").tobytes()
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)
    return path


def normalize(data, peak=0.97):
    data = np.asarray(data, dtype=np.float32)
    m = float(np.max(np.abs(data))) if len(data) else 0.0
    if m < 1e-6:
        return data
    return data * (peak / m)


def load_pack_audio(pack, sr=SR, progress=None):
    """Laedt alle Original-Samples und den Backing Track."""
    total = len(pack.lines) + 1
    for i, line in enumerate(pack.lines):
        line.audio = read_wav_mono(line.path, sr)
        line.duration = len(line.audio) / float(sr)
        if progress:
            progress((i + 1) / float(total))
    pack.backing_audio = (read_wav_mono(pack.backing, sr)
                          if pack.backing else None)
    pack.video_duration = pc.probe_duration(pack.video)
    if progress:
        progress(1.0)
    return pack


# ==========================================================================
#  Analyse / analysis
# ==========================================================================

def trim_silence(data, sr=SR, rel=0.08, pad=0.04, frame_ms=20):
    """
    Schneidet Stille vorn und hinten weg. Damit kostet ein spaeter
    Einsatz keine Punkte - nur der Verlauf selbst zaehlt.
    """
    data = np.asarray(data, dtype=np.float32)
    hop = max(1, int(sr * frame_ms / 1000.0))
    usable = (len(data) // hop) * hop
    if usable < hop * 2:
        return data
    rms = np.sqrt((data[:usable].reshape(-1, hop) ** 2).mean(axis=1))
    peak = float(rms.max())
    if peak < 1e-6:
        return data
    active = np.nonzero(rms >= peak * rel)[0]
    if not len(active):
        return data
    a = max(0, int(active[0] * hop - pad * sr))
    b = min(len(data), int((active[-1] + 1) * hop + pad * sr))
    return data[a:b]


def rms_db(data):
    data = np.asarray(data, dtype=np.float32)
    if not len(data):
        return -120.0
    r = float(np.sqrt((data ** 2).mean()))
    return 20.0 * np.log10(max(r, 1e-9))


# ==========================================================================
#  Video-Frames
# ==========================================================================

def frames_dir_for(pack):
    key = re.sub(r"[^\w]+", "_", os.path.normpath(pack.folder))[-90:]
    return os.path.join(CACHE_DIR, key)


def pack_duration(pack):
    """Laenge des Videos - einmal ermittelt, danach gemerkt."""
    if not pack.video_duration:
        try:
            pack.video_duration = pc.probe_duration(pack.video)
        except Exception:
            pack.video_duration = 0.0
    return pack.video_duration


def thumb_path(pack):
    return os.path.join(CACHE_DIR, "thumbs", os.path.basename(frames_dir_for(pack)) + ".jpg")


def make_thumb(pack, width=320):
    """Vorschaubild fuer das Menue. Gibt den Pfad zurueck oder None."""
    path = thumb_path(pack)
    try:
        if os.path.isfile(path) and \
                os.path.getmtime(path) >= os.path.getmtime(pack.video):
            return path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Nicht das allererste Bild - das ist oft schwarz.
        at = min(2.0, pack_duration(pack) / 3.0)
        pc.run([pc.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
                "-ss", "%.3f" % at, "-i", pack.video, "-frames:v", "1",
                "-vf", "scale=%d:-2" % int(width), "-q:v", "4", path])
        return path if os.path.isfile(path) else None
    except Exception:
        return None


def extract_frames(pack, fps=FRAME_FPS, width=FRAME_W, log=None, force=False):
    """
    Zerlegt das OGV vorab in JPEGs. Umgeht damit jede Codec-Frage
    bei der Wiedergabe - genau der Punkt, an dem das Original haengt.
    """
    outdir = frames_dir_for(pack)
    stamp = os.path.join(outdir, "done.txt")
    want = "%d %d" % (int(fps), int(width))
    if force and os.path.isdir(outdir):
        shutil.rmtree(outdir, ignore_errors=True)
    if os.path.isfile(stamp):
        try:
            with open(stamp, "r", encoding="utf-8") as f:
                have = f.read().strip()
        except Exception:
            have = ""
        if have == want:
            pack.frames = sorted(glob.glob(os.path.join(outdir, "f*.jpg")))
            pack.fps = float(fps)
            if pack.frames:
                return pack.frames
        # andere Aufloesung -> neu erzeugen
        shutil.rmtree(outdir, ignore_errors=True)
    os.makedirs(outdir, exist_ok=True)
    pc.run([pc.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
            "-i", pack.video,
            "-vf", "fps=%d,scale=%d:-2" % (int(fps), int(width)),
            "-q:v", "5", os.path.join(outdir, "f%05d.jpg")], log=log)
    pack.frames = sorted(glob.glob(os.path.join(outdir, "f*.jpg")))
    pack.fps = float(fps)
    with open(stamp, "w", encoding="utf-8") as f:
        f.write(want)
    return pack.frames


def frame_at(pack, seconds):
    """Index des Bildes zum Zeitpunkt / frame index for a time."""
    if not pack.frames:
        return None
    i = int(round(seconds * pack.fps))
    return max(0, min(len(pack.frames) - 1, i))


# ==========================================================================
#  Dub-Mix rendern
# ==========================================================================

def fit_len(data, n):
    """
    Bringt ein Array auf genau n Werte. Noetig, weil
    int(len(x)/sr*sr) nicht immer wieder len(x) ergibt - sonst knallt
    das Mischen von Aufnahme und Backing Track bei ~8% aller Cliplaengen.
    """
    data = np.asarray(data, dtype=np.float32)
    n = max(0, int(n))
    if len(data) == n:
        return data
    out = np.zeros(n, dtype=np.float32)
    m = min(n, len(data))
    out[:m] = data[:m]
    return out


def slice_audio(data, start, duration, sr=SR):
    """Schneidet einen Bereich heraus, mit Nullen aufgefuellt."""
    if data is None:
        return np.zeros(int(duration * sr), dtype=np.float32)
    a = int(max(0.0, start) * sr)
    n = int(duration * sr)
    out = np.zeros(n, dtype=np.float32)
    chunk = data[a:a + n]
    out[:len(chunk)] = chunk
    return out


def render_dub(pack, sr=SR, duck=0.18, log=None):
    """
    Legt alle Aufnahmen an ihre Zeitstempel ueber den Backing Track.
    Zeilen ohne Aufnahme behalten das Original - so wie es der
    Dub-Guide fuer nicht gewaehlte Figuren beschreibt.
    """
    voices, back = render_dub_parts(pack, sr, duck)
    return normalize(voices + back, 0.97)


def render_dub_parts(pack, sr=SR, duck=0.18):
    """
    Wie render_dub, aber Stimmen und Hintergrund getrennt (gleich lang,
    nicht normalisiert) - damit der Hintergrund leiser gedreht werden kann.
    Voices and background separately, so the background can be turned down.
    """
    total = max(pack.video_duration, 0.1)
    for line in pack.lines:
        total = max(total, line.end + 1.0)
    n = int(total * sr) + sr

    backing = getattr(pack, "backing_audio", None)
    if backing is not None:
        base = np.zeros(n, dtype=np.float32)
        base[:min(n, len(backing))] = backing[:n]
        have_backing = True
    else:
        original = read_wav_mono(pack.video, sr)
        base = np.zeros(n, dtype=np.float32)
        base[:min(n, len(original))] = original[:n]
        have_backing = False

    voices = np.zeros(n, dtype=np.float32)
    for line in pack.lines:
        a = int(line.start * sr)
        if line.take is not None and len(line.take):
            take = normalize(np.asarray(line.take, dtype=np.float32), 0.92)
            if not have_backing:
                # Original an dieser Stelle leiser ziehen
                b = min(n, a + max(len(take), int(line.duration * sr)))
                base[a:b] *= duck
            b = min(n, a + len(take))
            voices[a:b] += take[:b - a]
        elif line.audio is not None and have_backing:
            b = min(n, a + len(line.audio))
            voices[a:b] += line.audio[:b - a] * 0.9

    return voices, base


def mix_parts(voices, back, peak=0.97):
    """
    Skaliert Stimmen + Hintergrund so, dass die Summe bei gain=1 den
    Spitzenwert erreicht. Liefert (voices, back) fertig zum Mischen.
    """
    voices = np.asarray(voices, dtype=np.float32)
    back = fit_len(np.asarray(back, dtype=np.float32), len(voices))
    m = float(np.max(np.abs(voices + back))) if len(voices) else 0.0
    s = peak / m if m > 1e-6 else 1.0
    return voices * s, back * s


def export_dub_video(pack, mixed_audio, out_path, sr=SR, log=None):
    """Schreibt Video + eigener Tonspur als MP4 zum Weitergeben."""
    tmp_wav = tempfile.mktemp(suffix=".wav")
    write_wav_mono(tmp_wav, mixed_audio, sr)
    try:
        pc.run([pc.ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
                "-i", pack.video, "-i", tmp_wav,
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
                "-c:a", "aac", "-b:a", "192k", "-shortest", out_path], log=log)
    finally:
        if os.path.exists(tmp_wav):
            os.remove(tmp_wav)
    return out_path


# ==========================================================================
#  Mikrofon / microphone
# ==========================================================================

def audio_backend():
    """Gibt das sounddevice-Modul zurueck oder None."""
    try:
        import sounddevice as sd
        return sd
    except Exception:
        return None


ENV_MS = 20          # Aufloesung der laufenden Huellkurve / live envelope


class Mic(object):
    """Aufnahme, optional mit gleichzeitiger Wiedergabe des Backing Tracks."""

    def __init__(self, sr=SR):
        self.sr = sr
        self.sd = audio_backend()
        self._stream = None
        self._chunks = []
        self._env = []                                  # Spitzenwerte je Fenster
        self._env_step = max(1, int(sr * ENV_MS / 1000.0))
        self._buf = np.zeros(0, dtype=np.float32)
        self._out = None                                # Ausgabe von play_mix
        self.back_gain = 1.0                            # Hintergrund, live

    @property
    def available(self):
        return self.sd is not None

    def devices(self):
        if not self.sd:
            return []
        out = []
        for i, d in enumerate(self.sd.query_devices()):
            if d.get("max_input_channels", 0) > 0:
                out.append((i, d.get("name", "?")))
        return out

    def default_name(self):
        """Name des Standard-Mikrofons von Windows, sonst ''."""
        if not self.sd:
            return ""
        try:
            return self.sd.query_devices(kind="input").get("name", "")
        except Exception:
            return ""

    def start(self, playback=None, device=None, mix=False):
        """
        playback: Float-Array, das waehrend der Aufnahme laufen soll.
        device None: das Standard-Mikrofon von Windows.
        mix: playback ist Hintergrund und folgt back_gain (play_mix).
        """
        if not self.sd:
            raise RuntimeError("sounddevice fehlt / missing")
        self._chunks = []
        self._env = []
        self._env_step = max(1, int(self.sr * ENV_MS / 1000.0))
        self._buf = np.zeros(0, dtype=np.float32)

        def cb(indata, frames, time_info, status):
            data = np.asarray(indata[:, 0], dtype=np.float32).copy()
            self._chunks.append(data)
            # Spitzenwert je 20-ms-Fenster mitschreiben, damit die
            # Oberflaeche die Aufnahme live zeichnen kann.
            buf = data if not len(self._buf) else \
                np.concatenate([self._buf, data])
            step = self._env_step
            k = len(buf) // step
            if k:
                blocks = buf[:k * step].reshape(k, step)
                self._env.extend(np.abs(blocks).max(axis=1).tolist())
                buf = buf[k * step:]
            self._buf = buf

        kwargs = {"samplerate": self.sr, "channels": 1, "callback": cb,
                  "dtype": "float32"}
        if device is not None:
            kwargs["device"] = device
        self._stream = self.sd.InputStream(**kwargs)
        self._stream.start()
        if playback is not None and len(playback):
            if mix:
                self.play_mix(None, playback)
                return
            try:
                self.sd.play(np.asarray(playback, dtype=np.float32), self.sr)
            except Exception:
                pass

    def stop(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self._close_out()
        try:
            if self.sd:
                self.sd.stop()
        except Exception:
            pass
        if not self._chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(self._chunks).astype(np.float32)

    def envelope(self):
        """Bisher aufgenommene Huellkurve und ihre Schrittweite in Sekunden."""
        return list(self._env), self._env_step / float(self.sr)

    def level(self):
        """Aktueller Pegel 0..1 fuer die Aussteuerungsanzeige."""
        if not self._env:
            return 0.0
        return float(min(1.0, max(self._env[-5:]) * 1.4))

    def play(self, data):
        if not self.sd or data is None or not len(data):
            return
        try:
            self.sd.play(np.asarray(data, dtype=np.float32), self.sr)
        except Exception:
            pass

    def play_mix(self, voices, back):
        """
        Spielt Stimmen + Hintergrund (gleich lang, siehe mix_parts). Der
        Hintergrund folgt back_gain live - der Regler wirkt sofort.
        Plays voices + background; the background follows back_gain live.
        """
        if not self.sd or back is None:
            return
        self.stop_play()
        back = np.asarray(back, dtype=np.float32)
        voices = (np.zeros(len(back), dtype=np.float32) if voices is None
                  else np.asarray(voices, dtype=np.float32))
        back = fit_len(back, len(voices))
        pos = [0]

        def cb(outdata, frames, time_info, status):
            a = pos[0]
            b = min(len(voices), a + frames)
            out = voices[a:b] + back[a:b] * self.back_gain
            np.clip(out, -1.0, 1.0, out=out)
            outdata[:b - a, 0] = out
            outdata[b - a:] = 0
            pos[0] = b
            if b >= len(voices):
                raise self.sd.CallbackStop

        try:
            self._out = self.sd.OutputStream(samplerate=self.sr, channels=1,
                                             dtype="float32", callback=cb)
            self._out.start()
        except Exception:
            self._out = None

    def _close_out(self):
        out, self._out = self._out, None
        if out is not None:
            try:
                out.stop()
                out.close()
            except Exception:
                pass

    def stop_play(self):
        self._close_out()
        try:
            if self.sd:
                self.sd.stop()
        except Exception:
            pass

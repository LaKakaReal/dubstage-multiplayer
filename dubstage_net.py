# -*- coding: utf-8 -*-
"""
dubstage_net.py  --  Mehrspieler fuer DubStage / multiplayer for DubStage.

Koop: Der Host verteilt die Zeilen eines Packs auf die Mitspieler, jeder
nimmt seine Zeilen am eigenen Rechner auf, die Aufnahmen landen beim Host
und von dort bei allen anderen. Das Finale rendert jeder selbst.

Co-op: the host splits a pack's lines between the players, everyone records
their own lines on their own PC, takes go to the host and from there to all
others. Everyone renders the finale locally.

Nur HTTP + JSON mit Long-Polling - laeuft so direkt ueber IP:Port und
genauso durch einen Cloudflare Quick Tunnel. Keine GUI hier drin.
"""

import hashlib
import io
import json
import mimetypes
import os
import random
import re
import shutil
import socket
import string
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np

import dubforge_core as pc
import dubstage_core as ds

DEFAULT_PORT = 47800
NET_DIR = os.path.join(ds.PACKS_DIR, "_net")   # Packs von anderen Hosts
MAX_TAKE_BYTES = 20 * 1024 * 1024
POLL_WAIT = 20.0          # Long-Poll-Dauer in Sekunden
GIVE_UP_AFTER = 30.0      # so lange ohne Verbindung, dann Abbruch
ONLINE_WINDOW = 45.0      # zuletzt gesehen vor weniger als ... = online
USER_AGENT = "DubStage-Multiplayer/1"
WEB_CLIENT = os.path.join(ds.APP_DIR, "web", "client.html")
WEB_VIDEO_W = 960         # Breite des Videos fuer Browser-Gaeste

COLORS = ["#25d3a4", "#ff8a5c", "#5cb8ff", "#e070ff", "#ffd84d",
          "#ff5c8a", "#8aff5c", "#5cffe9"]


class NetError(Exception):
    """Fehler mit Text fuer den Spieler / error with a user-facing message."""


# ==========================================================================
#  Hilfen / helpers
# ==========================================================================

def pack_files(folder):
    """Die Dateien, die zum Pack gehoeren - nur die oberste Ebene."""
    out = []
    for f in sorted(os.listdir(folder)):
        p = os.path.join(folder, f)
        if os.path.isfile(p):
            out.append(f)
    return out


def pack_hash(folder):
    """Fingerabdruck eines Packs: Namen und Groessen, dazu die Untertitel."""
    h = hashlib.sha1()
    for f in pack_files(folder):
        p = os.path.join(folder, f)
        h.update(f.encode("utf-8"))
        h.update(b"\0%d\0" % os.path.getsize(p))
    cap = os.path.join(folder, "_captions.json")
    if os.path.isfile(cap):
        with open(cap, "rb") as fh:
            h.update(fh.read())
    return h.hexdigest()


def build_pack_zip(folder, out_path):
    """Packt den Pack-Ordner ohne Kompression (Video ist schon komprimiert)."""
    tmp = out_path + ".part"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_STORED) as z:
        for f in pack_files(folder):
            z.write(os.path.join(folder, f), f)
    os.replace(tmp, out_path)
    return out_path


_BAD_NAME = re.compile(r"[\\/:]")


def safe_extract(zip_path, dest):
    """Entpackt nur flache, harmlose Dateinamen - nie ausserhalb von dest."""
    os.makedirs(dest, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            name = info.filename
            if (not name or name in (".", "..") or name.startswith(".")
                    or _BAD_NAME.search(name) or info.is_dir()):
                raise NetError("Unsafe file name in pack: %r" % name)
            target = os.path.join(dest, name)
            if os.path.dirname(os.path.abspath(target)) != \
                    os.path.abspath(dest):
                raise NetError("Unsafe file name in pack: %r" % name)
            with z.open(info) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
    return dest


def wav_bytes(data, sr=ds.SR):
    """Mono-Float-Array -> WAV-Bytes (16 bit)."""
    data = np.clip(np.asarray(data, dtype=np.float32), -1.0, 1.0)
    pcm = (data * 32767.0).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)
    return buf.getvalue()


def wav_from_bytes(raw, sr=ds.SR):
    """WAV-Bytes -> Mono-Float-Array in der Arbeits-Samplerate."""
    with wave.open(io.BytesIO(raw), "rb") as w:
        ch, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
        frames = w.readframes(w.getnframes())
    if width != 2:
        raise NetError("Unsupported WAV format")
    data = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        data = data.reshape(-1, ch).mean(axis=1)
    if rate != sr and len(data):
        n = int(round(len(data) * sr / float(rate)))
        data = np.interp(np.linspace(0, len(data) - 1, n),
                         np.arange(len(data)), data).astype(np.float32)
    return data


def _valid_wav(raw):
    try:
        with wave.open(io.BytesIO(raw), "rb") as w:
            return w.getsampwidth() == 2 and w.getnframes() > 0
    except Exception:
        return False


def line_groups(lines):
    """Zeilen nach Figur/Name gruppiert, in Reihenfolge des Auftretens."""
    groups = []
    index = {}
    for line in lines:
        key = line.name
        if key not in index:
            index[key] = len(groups)
            groups.append((key, []))
        groups[index[key]][1].append(line)
    return groups


def _line_len(line):
    return line.duration if line.duration > 0 else 1.0


def auto_assign(lines, player_ids):
    """
    Verteilt die Zeilen gleichmaessig. Ganze Figuren bleiben bei einem
    Spieler; gibt es weniger Figuren als Spieler, wird Zeile fuer Zeile
    verteilt, damit jeder etwas zu tun hat.
    """
    player_ids = list(player_ids)
    if not player_ids:
        return {}
    groups = line_groups(lines)
    if len(groups) < len(player_ids):
        units = [[l] for l in lines]
    else:
        units = [g[1] for g in groups]
    load = dict((p, 0.0) for p in player_ids)
    out = {}
    for unit in sorted(units, key=lambda u: -sum(_line_len(l) for l in u)):
        pid = min(player_ids, key=lambda p: (load[p], player_ids.index(p)))
        for l in unit:
            out[l.file] = pid
        load[pid] += sum(_line_len(l) for l in unit)
    return out


def room_code():
    alphabet = "".join(c for c in string.ascii_uppercase + string.digits
                       if c not in "O0I1L")
    rnd = random.SystemRandom()
    return "".join(rnd.choice(alphabet) for _ in range(6))


def lan_ip():
    """Die eigene Adresse im lokalen Netz (ohne etwas zu senden)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def normalize_address(addr, default_port=DEFAULT_PORT):
    """'1.2.3.4', '1.2.3.4:47800', 'https://x.trycloudflare.com/' -> Basis-URL."""
    addr = (addr or "").strip()
    if not addr:
        raise NetError("No address")
    if "://" not in addr:
        scheme = "https" if "trycloudflare.com" in addr.lower() else "http"
        addr = scheme + "://" + addr
    u = urllib.parse.urlsplit(addr)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise NetError("Invalid address: %s" % addr)
    host = u.hostname
    if ":" in host:                       # IPv6
        host = "[%s]" % host
    port = u.port
    if port is None and u.scheme == "http":
        port = default_port
    netloc = host if port is None else "%s:%d" % (host, port)
    return "%s://%s" % (u.scheme, netloc)


# ==========================================================================
#  Cloudflare Quick Tunnel
# ==========================================================================

def find_cloudflared():
    return pc.find_tool("cloudflared") or shutil.which("cloudflared")


_TUNNEL_URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def start_quick_tunnel(port, timeout=40.0):
    """Startet 'cloudflared tunnel --url ...' und wartet auf die oeffentliche URL."""
    exe = find_cloudflared()
    if not exe:
        raise NetError("cloudflared not found")
    flags = 0x08000000 if sys.platform == "win32" else 0   # CREATE_NO_WINDOW
    proc = subprocess.Popen(
        [exe, "tunnel", "--no-autoupdate", "--url",
         "http://127.0.0.1:%d" % port],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL, creationflags=flags)
    found = {}
    ready = threading.Event()

    def drain():
        # Weiterlesen, auch nach dem Fund - sonst laeuft die Pipe voll.
        for raw in iter(proc.stderr.readline, b""):
            if not ready.is_set():
                m = _TUNNEL_URL.search(raw.decode("utf-8", "replace"))
                if m:
                    found["url"] = m.group(0)
                    ready.set()
        ready.set()

    threading.Thread(target=drain, daemon=True).start()
    ready.wait(timeout)
    if "url" not in found:
        stop_process(proc)
        raise NetError("cloudflared did not report a tunnel address")
    return proc, found["url"]


def stop_process(proc):
    if proc is None:
        return
    try:
        proc.terminate()
        proc.wait(5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


# ==========================================================================
#  Raum / room (lebt beim Host)
# ==========================================================================

class Room(object):
    """Der gemeinsame Zustand. Alle Methoden sind threadsicher."""

    def __init__(self, pack, code=None):
        self.pack = pack
        self.code = code or room_code()
        self.pack_hash = pack_hash(pack.folder)
        self.pack_size = sum(os.path.getsize(os.path.join(pack.folder, f))
                             for f in pack_files(pack.folder))
        self.line_files = [l.file for l in pack.lines]
        self.version = 1
        self.phase = "lobby"
        self.players = {}         # id -> dict
        self.tokens = {}          # token -> id
        self.owner = {}           # line file -> player id
        self.takes = {}           # line file -> {"player", "rev"}
        self.take_data = {}       # line file -> WAV bytes
        self._next_id = 1
        self._rev = 0
        self._cond = threading.Condition()
        self._zip_lock = threading.Lock()
        self._zip_path = None
        self.host_id = None
        self.line_paths = dict((l.file, l.path) for l in pack.lines)
        self._web_lock = threading.Lock()
        self.web_state = "idle"   # idle | working | ready | failed
        self._web_path = None

    # --- intern
    def _bump(self):
        self.version += 1
        self._cond.notify_all()

    def _player_by_token(self, token):
        pid = self.tokens.get(token or "")
        if pid is None or self.players[pid].get("left"):
            return None
        return pid

    # --- Spieler
    def join(self, name, host=False):
        name = (name or "").strip()[:24] or "Player"
        with self._cond:
            taken = set(p["name"] for p in self.players.values()
                        if not p.get("left"))
            base, n = name, 2
            while name in taken:
                name = "%s %d" % (base, n)
                n += 1
            pid = "p%d" % self._next_id
            self._next_id += 1
            token = hashlib.sha1(os.urandom(16)).hexdigest()
            self.players[pid] = {
                "id": pid, "name": name, "host": host,
                "color": COLORS[(self._next_id - 2) % len(COLORS)],
                "ready": host, "progress": 1.0 if host else 0.0,
                "seen": time.time(), "left": False,
            }
            self.tokens[token] = pid
            if host:
                self.host_id = pid
                for f in self.line_files:
                    self.owner.setdefault(f, pid)
            self._bump()
            return pid, token

    def leave(self, token):
        with self._cond:
            pid = self._player_by_token(token)
            if pid is None:
                return
            self.players[pid]["left"] = True
            # Seine Zeilen fallen an den Host zurueck, Aufnahmen bleiben.
            for f, owner in list(self.owner.items()):
                if owner == pid and self.host_id:
                    self.owner[f] = self.host_id
            self._bump()

    def set_status(self, token, ready=None, progress=None):
        with self._cond:
            pid = self._player_by_token(token)
            if pid is None:
                return False
            p = self.players[pid]
            changed = False
            if ready is not None and bool(ready) != p["ready"]:
                p["ready"] = bool(ready)
                changed = True
            if progress is not None:
                progress = max(0.0, min(1.0, float(progress)))
                if abs(progress - p["progress"]) >= 0.01 or progress >= 1.0:
                    p["progress"] = progress
                    changed = True
            if changed:
                self._bump()
            return True

    def touch(self, token):
        pid = self.tokens.get(token or "")
        if pid is not None:
            self.players[pid]["seen"] = time.time()
        return pid

    # --- nur Host
    def assign(self, line_file, player_id):
        with self._cond:
            if line_file in self.owner and player_id in self.players:
                self.owner[line_file] = player_id
                self._bump()

    def assign_all(self, mapping):
        with self._cond:
            for f, pid in mapping.items():
                if f in self.owner and pid in self.players:
                    self.owner[f] = pid
            self._bump()

    def active_ids(self):
        with self._cond:
            return [pid for pid, p in sorted(self.players.items(),
                                             key=lambda kv: int(kv[0][1:]))
                    if not p.get("left")]

    def start(self):
        with self._cond:
            self.phase = "recording"
            self._bump()

    def back_to_lobby(self):
        with self._cond:
            self.phase = "lobby"
            self._bump()

    def close(self):
        """Spiel beendet - wartende Gaeste erfahren es sofort."""
        with self._cond:
            self.phase = "closed"
            self._bump()

    # --- Aufnahmen
    def put_take(self, token, line_file, raw):
        with self._cond:
            pid = self._player_by_token(token)
            if pid is None:
                return 403, "unknown player"
            if line_file not in self.owner:
                return 404, "unknown line"
            if self.owner[line_file] != pid:
                return 403, "not your line"
            if not _valid_wav(raw):
                return 400, "not a 16-bit WAV"
            self._rev += 1
            self.take_data[line_file] = raw
            self.takes[line_file] = {"player": pid, "rev": self._rev}
            self._bump()
            return 200, "ok"

    def delete_take(self, token, line_file):
        with self._cond:
            pid = self._player_by_token(token)
            if pid is None:
                return 403, "unknown player"
            if line_file not in self.owner:
                return 404, "unknown line"
            if self.owner[line_file] != pid:
                return 403, "not your line"
            self.take_data.pop(line_file, None)
            self.takes.pop(line_file, None)
            self._bump()
            return 200, "ok"

    def get_take(self, line_file):
        with self._cond:
            return self.take_data.get(line_file)

    # --- Zustand
    def snapshot(self):
        now = time.time()
        players = []
        for pid, p in sorted(self.players.items(),
                             key=lambda kv: int(kv[0][1:])):
            q = dict(p)
            q["online"] = (not p["left"]) and now - p["seen"] < ONLINE_WINDOW
            q.pop("seen", None)
            players.append(q)
        return {
            "version": self.version,
            "phase": self.phase,
            "pack": {"name": self.pack.name, "hash": self.pack_hash,
                     "size": self.pack_size, "lines": self.line_files},
            "players": players,
            "owner": dict(self.owner),
            "takes": dict(self.takes),
        }

    def wait_state(self, since, timeout=POLL_WAIT):
        with self._cond:
            self._cond.wait_for(lambda: self.version > since, timeout)
            return self.snapshot()

    def pack_meta(self):
        """Was ein Browser-Gast ueber den Pack wissen muss."""
        return {
            "name": self.pack.name,
            "duration": float(getattr(self.pack, "video_duration", 0) or 0),
            "backing": bool(self.pack.backing),
            "lines": [{"file": l.file, "start": l.start,
                       "duration": l.duration, "name": l.name,
                       "caption": l.caption} for l in self.pack.lines],
        }

    def prepare_web_video(self):
        """
        Stummes, leichtes MP4 fuer Browser-Gaeste - Chrome und Edge spielen
        kein OGV, und durch den Tunnel zaehlt jedes Megabyte. Einmal pro
        Pack, im Hintergrund, danach aus dem Cache.
        """
        with self._web_lock:
            if self.web_state != "idle":
                return
            path = os.path.join(ds.CACHE_DIR,
                                "net_%s_web.mp4" % self.pack_hash[:16])
            if os.path.isfile(path):
                self._web_path, self.web_state = path, "ready"
                return
            self.web_state = "working"

        def work():
            tmp = path + ".part.mp4"
            try:
                os.makedirs(ds.CACHE_DIR, exist_ok=True)
                pc.run([pc.ffmpeg(), "-y", "-hide_banner", "-loglevel",
                        "error", "-i", self.pack.video, "-an",
                        "-vf", "scale='min(%d,iw)':-2" % WEB_VIDEO_W,
                        "-c:v", "libx264", "-preset", "veryfast",
                        "-crf", "28", "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart", tmp], check=True)
                os.replace(tmp, path)
                self._web_path, self.web_state = path, "ready"
            except Exception as ex:
                print("DubStage: web video failed: %s" % ex)
                self.web_state = "failed"
                if os.path.exists(tmp):
                    os.remove(tmp)

        threading.Thread(target=work, daemon=True).start()

    def web_video(self):
        self.prepare_web_video()
        return self.web_state, self._web_path

    def pack_zip(self):
        with self._zip_lock:
            if self._zip_path and os.path.isfile(self._zip_path):
                return self._zip_path
            os.makedirs(ds.CACHE_DIR, exist_ok=True)
            path = os.path.join(ds.CACHE_DIR,
                                "net_%s.zip" % self.pack_hash[:16])
            if not os.path.isfile(path):
                build_pack_zip(self.pack.folder, path)
            self._zip_path = path
            return path


# ==========================================================================
#  HTTP-Server
# ==========================================================================

class _Handler(BaseHTTPRequestHandler):
    server_version = "DubStage"
    protocol_version = "HTTP/1.1"

    def log_message(self, *_a):
        pass

    @property
    def room(self):
        return self.server.room

    # --- Antworten
    def _send(self, code, body=b"", ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode("utf-8")
        elif isinstance(body, str):
            body = json.dumps({"error": body} if code >= 400
                              else {"ok": body}).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _body(self, limit):
        n = int(self.headers.get("Content-Length") or 0)
        if n < 0 or n > limit:
            raise ValueError("body too large")
        return self.rfile.read(n) if n else b""

    def _query(self):
        return urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)

    def _authorized(self):
        # <video src> und <audio src> koennen keine Header setzen - dort
        # steht der Raumcode in ?room=.
        code = self.headers.get("X-Room") or \
            self._query().get("room", [""])[0]
        if code.strip().upper() != self.room.code:
            self._send(403, "wrong room code")
            return False
        self.room.touch(self.headers.get("X-Token"))
        return True

    def _line_from_path(self, prefix="/take/"):
        name = urllib.parse.unquote(self.path.split("?", 1)[0][len(prefix):])
        return name if name in self.room.line_files else None

    # --- Methoden
    def do_GET(self):
        if self.path.split("?", 1)[0] in ("/", "/index.html") \
                and not self.headers.get("X-Room"):
            # Browser-Gaeste: die Web-App selbst, Beitreten mit Raumcode dort.
            self._send_web_client()
            return
        if not self._authorized():
            return
        path = self.path.split("?", 1)[0]
        if path == "/state":
            q = self._query()
            try:
                since = int(q.get("since", ["0"])[0])
            except ValueError:
                since = 0
            self._send(200, self.room.wait_state(since))
        elif path == "/pack.zip":
            self._send_file(self.room.pack_zip(), "application/zip")
        elif path == "/pack/meta":
            self._send(200, self.room.pack_meta())
        elif path == "/media/video":
            state, video = self.room.web_video()
            if state == "ready":
                self._send_file(video, "video/mp4")
            elif state == "failed":
                self._send(500, "video conversion failed")
            else:
                self._send(503, "preparing")
        elif path == "/media/backing":
            if self.room.pack.backing:
                self._send_file(self.room.pack.backing)
            else:
                self._send(404, "no backing track")
        elif path.startswith("/media/line/"):
            line = self._line_from_path("/media/line/")
            if line is None:
                self._send(404, "unknown line")
            else:
                self._send_file(self.room.line_paths[line])
        elif path.startswith("/take/"):
            line = self._line_from_path()
            raw = self.room.get_take(line) if line else None
            if raw is None:
                self._send(404, "no take")
            else:
                self._send(200, raw, "audio/wav")
        else:
            self._send(404, "not found")

    def _send_web_client(self):
        try:
            with open(WEB_CLIENT, "rb") as fh:
                body = fh.read()
        except OSError:
            body = (b"<!doctype html><meta charset=utf-8><p>A DubStage game "
                    b"is running here. Open DubStage and use Join game.")
        self._send(200, body, "text/html; charset=utf-8")

    def _send_file(self, path, ctype=None):
        """Datei mit Range-Unterstuetzung - Browser springen so im Video."""
        ctype = ctype or mimetypes.guess_type(path)[0] or \
            "application/octet-stream"
        size = os.path.getsize(path)
        start, end = 0, size - 1
        m = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range") or "")
        partial = bool(m and (m.group(1) or m.group(2)))
        if partial:
            if m.group(1):
                start = int(m.group(1))
                if m.group(2):
                    end = min(int(m.group(2)), size - 1)
            else:                                   # die letzten n Bytes
                start = max(0, size - int(m.group(2)))
            if start > end or start >= size:
                self.send_response(416)
                self.send_header("Content-Range", "bytes */%d" % size)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
        self.send_response(206 if partial else 200)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if partial:
            self.send_header("Content-Range",
                             "bytes %d-%d/%d" % (start, end, size))
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(path, "rb") as fh:
            fh.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = fh.read(min(256 * 1024, left))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)

    do_HEAD = do_GET

    def do_POST(self):
        if not self._authorized():
            return
        path = self.path.split("?", 1)[0]
        try:
            data = json.loads(self._body(64 * 1024) or b"{}")
        except Exception:
            self._send(400, "bad request")
            return
        token = self.headers.get("X-Token")
        if path == "/join":
            pid, token = self.room.join(data.get("name"))
            self._send(200, {"player": pid, "token": token,
                             "state": self.room.snapshot()})
        elif path == "/leave":
            self.room.leave(token)
            self._send(200, "ok")
        elif path == "/status":
            if self.room.set_status(token, data.get("ready"),
                                    data.get("progress")):
                self._send(200, "ok")
            else:
                self._send(403, "unknown player")
        else:
            self._send(404, "not found")

    def do_PUT(self):
        if not self._authorized():
            return
        if not self.path.startswith("/take/"):
            self._send(404, "not found")
            return
        line = self._line_from_path()
        if line is None:
            self._send(404, "unknown line")
            return
        try:
            raw = self._body(MAX_TAKE_BYTES)
        except ValueError:
            self._send(413, "take too large")
            return
        code, msg = self.room.put_take(self.headers.get("X-Token"), line, raw)
        self._send(code, msg)

    def do_DELETE(self):
        if not self._authorized():
            return
        line = self._line_from_path() if self.path.startswith("/take/") \
            else None
        if line is None:
            self._send(404, "unknown line")
            return
        code, msg = self.room.delete_take(self.headers.get("X-Token"), line)
        self._send(code, msg)


class Server(object):
    """HTTP-Server fuer einen Raum, laeuft in einem eigenen Thread."""

    def __init__(self, room, port=DEFAULT_PORT, host="0.0.0.0"):
        self.room = room
        try:
            self.httpd = ThreadingHTTPServer((host, port), _Handler)
        except OSError as ex:
            raise NetError("Port %d is not free (%s)" % (port, ex))
        self.httpd.daemon_threads = True
        self.httpd.room = room
        self.port = self.httpd.server_address[1]
        self._thread = threading.Thread(target=self.httpd.serve_forever,
                                        daemon=True)
        self._thread.start()

    def close(self):
        # Wartende Long-Polls bekommen noch "closed", dann ist Schluss.
        self.room.close()
        time.sleep(0.3)
        try:
            self.httpd.shutdown()
            self.httpd.server_close()
        except Exception:
            pass


# ==========================================================================
#  Client
# ==========================================================================

class Client(object):
    """Spricht mit einem Raum - beim Host genauso wie bei den Gaesten."""

    def __init__(self, address, code):
        self.base = normalize_address(address)
        self.code = (code or "").strip().upper()
        self.token = None
        self.player = None
        self.version = 0
        self._stop = threading.Event()
        self._thread = None

    # --- HTTP
    def _request(self, method, path, body=None, ctype=None, timeout=15.0):
        headers = {"X-Room": self.code, "User-Agent": USER_AGENT}
        if self.token:
            headers["X-Token"] = self.token
        if body is not None and not isinstance(body, bytes):
            body = json.dumps(body).encode("utf-8")
            ctype = "application/json"
        if ctype:
            headers["Content-Type"] = ctype
        req = urllib.request.Request(self.base + path, data=body,
                                     headers=headers, method=method)
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as ex:
            try:
                msg = json.loads(ex.read().decode("utf-8")).get("error")
            except Exception:
                msg = None
            finally:
                ex.close()
            if ex.code == 403 and msg == "wrong room code":
                raise NetError("wrong room code")
            raise NetError(msg or "HTTP %d" % ex.code)
        except (urllib.error.URLError, socket.timeout, OSError) as ex:
            reason = getattr(ex, "reason", ex)
            raise NetError("Cannot reach %s (%s)" % (self.base, reason))

    def _json(self, method, path, body=None, timeout=15.0):
        with self._request(method, path, body, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    # --- Aktionen
    def join(self, name):
        res = self._json("POST", "/join", {"name": name})
        self.token = res["token"]
        self.player = res["player"]
        return res["state"]

    def leave(self):
        try:
            self._json("POST", "/leave", {}, timeout=4.0)
        except Exception:
            pass

    def set_status(self, ready=None, progress=None):
        body = {}
        if ready is not None:
            body["ready"] = ready
        if progress is not None:
            body["progress"] = progress
        self._json("POST", "/status", body)

    def state(self, since=0, timeout=POLL_WAIT + 10):
        return self._json("GET", "/state?since=%d" % since, timeout=timeout)

    def download_pack(self, state, progress=None):
        """
        Holt den Pack des Hosts nach packs/_net, falls noch nicht da.
        Gibt den Ordner zurueck.
        """
        info = state["pack"]
        dest = os.path.join(NET_DIR, "%s-%s" % (pc.safe_name(info["name"],
                                                            "pack"),
                                                info["hash"][:8]))
        if os.path.isdir(dest) and pack_hash(dest) == info["hash"]:
            if progress:
                progress(1.0)
            return dest
        os.makedirs(NET_DIR, exist_ok=True)
        tmp_zip = tempfile.mktemp(suffix=".zip", dir=NET_DIR)
        tmp_dir = dest + ".part"
        try:
            with self._request("GET", "/pack.zip", timeout=60.0) as r, \
                    open(tmp_zip, "wb") as out:
                total = int(r.headers.get("Content-Length") or
                            info.get("size") or 0)
                got = 0
                last = 0.0
                while True:
                    chunk = r.read(256 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    got += len(chunk)
                    now = time.time()
                    if progress and total and now - last > 0.25:
                        last = now
                        progress(min(0.99, got / float(total)))
            if os.path.isdir(tmp_dir):
                shutil.rmtree(tmp_dir, True)
            safe_extract(tmp_zip, tmp_dir)
            if pack_hash(tmp_dir) != info["hash"]:
                raise NetError("The pack arrived damaged - please try again")
            if os.path.isdir(dest):
                shutil.rmtree(dest, True)
            os.replace(tmp_dir, dest)
        finally:
            if os.path.exists(tmp_zip):
                os.remove(tmp_zip)
            if os.path.isdir(tmp_dir):
                shutil.rmtree(tmp_dir, True)
        if progress:
            progress(1.0)
        return dest

    def upload_take(self, line_file, data):
        path = "/take/" + urllib.parse.quote(line_file)
        with self._request("PUT", path, wav_bytes(data), "audio/wav",
                           timeout=60.0) as r:
            r.read()

    def delete_take(self, line_file):
        path = "/take/" + urllib.parse.quote(line_file)
        with self._request("DELETE", path) as r:
            r.read()

    def fetch_take(self, line_file):
        path = "/take/" + urllib.parse.quote(line_file)
        with self._request("GET", path, timeout=60.0) as r:
            return wav_from_bytes(r.read())

    # --- Abfrage im Hintergrund
    def start_polling(self, sink):
        """
        sink(kind, payload) wird aus dem Hintergrund-Thread gerufen:
        ("net", state), ("net_wait", text), ("net_lost", text).
        """
        self._stop.clear()

        def loop():
            failing_since = None
            delay = 1.0
            while not self._stop.is_set():
                try:
                    st = self.state(self.version)
                except NetError as ex:
                    if self._stop.is_set():
                        break
                    now = time.time()
                    if failing_since is None:
                        failing_since = now
                        sink("net_wait", str(ex))
                    if now - failing_since > GIVE_UP_AFTER:
                        sink("net_lost", str(ex))
                        break
                    self._stop.wait(delay)
                    delay = min(5.0, delay * 1.6)
                    continue
                if failing_since is not None:
                    failing_since = None
                    delay = 1.0
                    sink("net_back", None)
                if st.get("version", 0) != self.version:
                    self.version = st["version"]
                    sink("net", st)

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop_polling(self):
        self._stop.set()

# -*- coding: utf-8 -*-
"""
DubStage  --  Szenen nachsprechen und am Stueck mit eigener Stimme abspielen.
DubStage  --  dub a scene line by line and play it back with your own voice.

Passt zu den Dub-Packs, die DubForge baut.
"""

import os
import sys
import json
import time
import queue
import textwrap
import tempfile
import threading
import traceback
import webbrowser

import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dubforge_core as pc
import dubstage_core as ds
import dubstage_net as net
import updater as upd
import appwin

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(APP_DIR, "dubstage_settings.json")
OUT_DIR = os.path.join(APP_DIR, "dubs")

try:
    from PIL import Image, ImageTk
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False

# ------------------------------------------------------------------ Palette
BG_TOP = "#171a2e"
BG_BOT = "#0a0b12"
PANEL = "#1a1e30"
PANEL_HI = "#242a42"
EDGE = "#333a5c"
TXT = "#eef1ff"
DIM = "#8a92b4"
ACC = "#7c5cff"
ACC_HI = "#9b83ff"
TEAL = "#25d3a4"
TEAL_HI = "#4ee5bb"
RED = "#ff4f6d"
RED_HI = "#ff7b92"
GOLD = "#ffc861"
BAN = "#332e5e"          # Update-Banner / update banner
BAN_TXT = "#241f47"
WAVE_ORIG = "#3c4470"          # Silhouette des Originals
WAVE_ORIG_TXT = "#7079ad"

TAIL = 0.7            # Nachlauf der Aufnahme / recording tail in seconds
THUMB_W, THUMB_H = 112, 63    # Vorschaubild im Menue, 16:9


# ==========================================================================
LANG = "de"


def set_lang(code):
    global LANG
    LANG = "en" if str(code).lower().startswith("en") else "de"
    pc.set_lang(LANG)


T = {
    "title":      ("DubStage", "DubStage"),
    "tagline":    ("Sprich die Szene selbst ein.", "Dub the scene yourself."),
    "pick":       ("Wähle einen Dub-Pack", "Choose a dub pack"),
    "no_packs":   ("Kein Dub-Pack gefunden.",
                   "No dub pack found."),
    "no_packs_2": ("Ein Dub-Pack braucht ein dub_video (mp4 oder ogv) und "
                   "Clips mit\nZeitstempel im Namen - genau das, was DubForge "
                   "mit Haken bei\n'Mit Video' erzeugt.",
                   "A dub pack needs a dub_video (mp4 or ogv) and clips with "
                   "a\ntimestamp in the name - exactly what DubForge produces "
                   "with\n'With video' ticked."),
    "lines_n":    ("%d Zeilen", "%d lines"),
    "with_back":  ("mit Backing", "with backing"),
    "no_back":    ("ohne Backing", "no backing"),
    "rescan":     ("Neu suchen", "Rescan"),
    "add_folder": ("Hinzufügen …", "Add …"),
    "add_dir":    ("Ordner mit Packs …", "Folder with packs …"),
    "add_archive": ("Zip oder RAR …", "Zip or RAR …"),
    "unpacking":  ("Entpacke %d Archiv(e) …", "Unpacking %d archive(s) …"),
    "unpack_fail": ("Konnte nicht entpackt werden:\n\n%s",
                    "Could not be unpacked:\n\n%s"),
    "no_pack_in": ("Kein Dub-Pack darin gefunden:\n\n%s",
                   "No dub pack found inside:\n\n%s"),
    "mic":        ("Mikrofon", "Microphone"),
    "mic_test":   ("Testen", "Test"),
    "mic_default": ("Windows-Standard (%s)", "Windows default (%s)"),
    "mic_run":    ("Sprich jetzt ...", "Speak now ..."),
    "mic_ok":     ("Pegel %.0f dB - passt", "Level %.0f dB - good"),
    "mic_low":    ("Pegel %.0f dB - zu leise", "Level %.0f dB - too quiet"),
    "mic_none":   ("Nichts angekommen - anderes Gerät wählen",
                   "Nothing arrived - pick another device"),
    "start":      ("Loslegen", "Start"),
    "loading":    ("Pack wird vorbereitet ...", "Preparing the pack ..."),
    "no_sd":      ("Mikrofon nicht nutzbar: Paket 'sounddevice' fehlt. "
                   "Bitte das Setup erneut ausführen.",
                   "Microphone unavailable: package 'sounddevice' missing. "
                   "Please run the setup again."),
    "no_pil":     ("Videoanzeige braucht 'Pillow'. Bitte das Setup erneut "
                   "ausführen.",
                   "Video display needs 'Pillow'. Please run the setup again."),

    "menu":       ("Menü", "Menu"),
    "line_of":    ("Zeile %d / %d", "Line %d / %d"),
    "play_orig":  ("Original", "Original"),
    "rec":        ("Aufnehmen", "Record"),
    "rec_again":  ("Nochmal aufnehmen", "Record again"),
    "play_take":  ("Meine Aufnahme", "My take"),
    "stop":       ("Stopp", "Stop"),
    "skip":       ("Zeile leer lassen", "Leave line empty"),
    "prev":       ("Zurück", "Back"),
    "next":       ("Weiter", "Next"),
    "finish":     ("Fertig", "Done"),
    "recording":  ("AUFNAHME", "RECORDING"),
    "go":         ("LOS", "GO"),
    "hint":       ("Original anhören, dann aufnehmen. Beliebig oft.",
                   "Listen to the original, then record. As often as you like."),
    "no_take":    ("noch nichts aufgenommen", "nothing recorded yet"),
    "take_len":   ("Aufnahme %.1f s", "Take %.1f s"),
    "legend_orig": ("Original", "Original"),
    "legend_take": ("Deine Aufnahme", "Your take"),
    "recorded_n": ("%d von %d Zeilen aufgenommen",
                   "%d of %d lines recorded"),

    "finale":     ("Deine Szene", "Your scene"),
    "play_all":   ("Abspielen", "Play"),
    "save":       ("Als Video speichern", "Save as video"),
    "back_edit":  ("Zurück zu den Zeilen", "Back to the lines"),
    "saving":     ("Video wird geschrieben ...", "Writing the video ..."),
    "saved":      ("Gespeichert:\n%s", "Saved:\n%s"),
    "leave_q":    ("Zurück zum Menü? Die Aufnahmen gehen verloren.",
                   "Back to the menu? The takes will be lost."),
    "err":        ("Fehler", "Error"),
    "quiet_hint": ("sehr leise - lauter sprechen", "very quiet - speak up"),

    # --- Mehrspieler / multiplayer
    "host":       ("Spiel hosten", "Host game"),
    "join":       ("Beitreten", "Join game"),
    "host_t":     ("Spiel hosten", "Host a game"),
    "join_t":     ("Spiel beitreten", "Join a game"),
    "your_name":  ("Dein Name", "Your name"),
    "port":       ("Port", "Port"),
    "address":    ("Adresse", "Address"),
    "room_code":  ("Raumcode", "Room code"),
    "cancel":     ("Abbrechen", "Cancel"),
    "use_tunnel": ("Cloudflare Quick Tunnel starten",
                   "Start a Cloudflare quick tunnel"),
    "tunnel_ok":  ("Freunde treten dann über eine …trycloudflare.com-Adresse "
                   "bei – ohne Portfreigabe.",
                   "Friends then join via a …trycloudflare.com address – "
                   "no port forwarding needed."),
    "tunnel_missing": ("cloudflared nicht gefunden. Das Setup erneut "
                       "ausführen (cloudflared anhaken) oder winget install "
                       "Cloudflare.cloudflared, um ohne Portfreigabe zu "
                       "spielen.",
                       "cloudflared not found. Run the setup again (tick "
                       "cloudflared) or winget install Cloudflare.cloudflared "
                       "to play without port forwarding."),
    "tunnel_fail": ("Der Cloudflare-Tunnel ließ sich nicht starten:\n%s\n\n"
                    "Das Spiel läuft trotzdem – Freunde brauchen dann deine "
                    "IP und eine Portfreigabe.",
                    "The Cloudflare tunnel could not be started:\n%s\n\n"
                    "The game runs anyway – friends then need your IP and "
                    "a forwarded port."),
    "bad_port":   ("Ungültiger Port.", "Invalid port."),
    "need_addr":  ("Bitte Adresse und Raumcode eingeben.",
                   "Please enter the address and room code."),
    "net_connecting": ("Verbinde ...", "Connecting ..."),
    "net_join_fail": ("Beitreten fehlgeschlagen", "Could not join"),
    "lobby":      ("Lobby", "Lobby"),
    "net_leave":  ("Verlassen", "Leave"),
    "copy":       ("Kopieren", "Copy"),
    "copied":     ("In die Zwischenablage kopiert", "Copied to clipboard"),
    "share_addr": ("Schick deinen Freunden Adresse + Raumcode",
                   "Send your friends an address + the room code"),
    "joined_addr": ("Verbunden mit", "Connected to"),
    "addr_tunnel": ("Cloudflare-Tunnel (für die App)",
                    "Cloudflare tunnel (for the app)"),
    "addr_browser": ("Browser-Link – ohne App, mit Raumcode",
                     "Browser link – no app needed, code included"),
    "addr_lan":   ("LAN / VPN (Tailscale, Radmin ...)",
                   "LAN / VPN (Tailscale, Radmin ...)"),
    "addr_inet":  ("Internet", "Internet"),
    "addr_inet_v": ("deine öffentliche IP:%d – Port im Router freigeben",
                    "your public IP:%d – forward the port in your router"),
    "players":    ("Spieler", "Players"),
    "you":        ("du", "you"),
    "host_tag":   ("Host", "host"),
    "st_ready":   ("bereit", "ready"),
    "st_dl":      ("Pack %d%%", "pack %d%%"),
    "st_prep":    ("bereitet vor", "preparing"),
    "st_off":     ("offline", "offline"),
    "roles":      ("Wer spricht was", "Who voices what"),
    "roles_hint": ("Klicken: wer spricht die Rolle (auch frei)",
                   "Click to change who voices it (or free it)"),
    "roles_pick": ("Freie Rolle anklicken zum Nehmen, eigene zum Abgeben",
                   "Click a free role to take it, click yours to give it back"),
    "role_free":  ("frei", "free"),
    "role_taken": ("Diese Rolle hat schon jemand.",
                   "Someone already has that role."),
    "ready_btn":  ("Bereit ✓", "Ready ✓"),
    "wait_title": ("Warten auf die anderen", "Waiting for the others"),
    "wait_sub":   ("Sobald alle bereit sind, wird die Szene zusammengesetzt.",
                   "Once everyone is ready, the scene is put together."),
    "lines_done": ("%d / %d Zeilen", "%d / %d lines"),
    "st_done":    ("bereit ✓", "ready ✓"),
    "st_working": ("nimmt noch auf", "still recording"),
    "replay_mine": ("Meine Zeilen abspielen", "Replay my lines"),
    "back_mine":  ("Zurück zu meinen Zeilen", "Back to my lines"),
    "finish_now": ("Jetzt fertigstellen", "Finish now"),
    "assembling": ("Szene wird zusammengesetzt ...",
                   "Putting the scene together ..."),
    "assembling_n": ("%d von %d Aufnahmen da", "%d of %d takes here"),
    "no_takes_mine": ("Du hast noch nichts aufgenommen.",
                      "You haven't recorded anything yet."),
    "unassigned_n": ("%d Zeilen ohne Sprecher – dort bleibt das Original.",
                     "%d lines have no one – they keep the original voice."),
    "by_line":    ("Nach Zeilen", "By line"),
    "by_char":    ("Nach Figuren", "By character"),
    "dl_pack":    ("Pack wird geladen ...", "Downloading the pack ..."),
    "auto_split": ("Automatisch aufteilen", "Auto split"),
    "net_start":  ("Los geht's", "Start"),
    "wait_ready": ("Warte, bis alle den Pack haben ...",
                   "Waiting for everyone to get the pack ..."),
    "can_start":  ("Alle bereit.", "Everyone is ready."),
    "wait_host":  ("Warte auf den Host ...", "Waiting for the host to start ..."),
    "voiced_by":  ("gesprochen von %s", "voiced by %s"),
    "their_take": ("Aufnahme anhören", "Play take"),
    "legend_their": ("Aufnahme von %s", "%s's take"),
    "bg_vol":     ("Hintergrund", "Background"),
    "net_yours_left": ("deine fehlen noch: %d", "yours left: %d"),
    "net_waiting": ("warte auf %s", "waiting for %s"),
    "net_unsent": ("%d noch nicht gesendet", "%d not sent yet"),
    "net_trouble": ("Verbindung hakt – versuche es weiter ...",
                    "Connection trouble – retrying ..."),
    "net_lost_t": ("Verbindung verloren", "Connection lost"),
    "net_closed": ("Der Host hat das Spiel beendet.",
                   "The host ended the game."),
    "net_leave_host_q": ("Spiel für alle beenden?",
                         "End the game for everyone?"),
    "net_leave_q": ("Spiel verlassen? Deine Aufnahmen bleiben beim Host.",
                    "Leave the game? Your takes stay with the host."),
    "net_new_takes": ("Neue Aufnahmen sind da – zurück zu den Zeilen und "
                      "wieder 'Fertig', um sie zu hören.",
                      "New takes arrived – go back to the lines and press "
                      "Done again to hear them."),
    "net_bad_pack": ("Der empfangene Pack ist unvollständig.",
                     "The received pack is incomplete."),

    # --- Update
    "upd_head":  ("Version %s ist da", "Version %s is out"),
    "upd_sub":    ("Du hast %s", "You have %s"),
    "upd_more":   ("Was ist neu", "What's new"),
    "upd_less":   ("Zuklappen", "Collapse"),
    "upd_now":    ("Aktualisieren", "Update"),
    "upd_later":  ("Später", "Later"),
    "upd_nonotes": ("Zu dieser Version wurde kein Text hinterlegt.",
                    "No description was published for this version."),
    "upd_ask_t":  ("Update einspielen?", "Install update?"),
    "upd_ask":    ("DubForge und DubStage werden auf %s aktualisiert.\n\n"
                   "Die App schließt sich, die Dateien werden getauscht "
                   "und die App startet neu.\n"
                   "Packs, Aufnahmen und Einstellungen bleiben unberührt.\n\n"
                   "Fortfahren?",
                   "DubForge and DubStage will be updated to %s.\n\n"
                   "The app closes, the files are replaced and the app "
                   "starts again.\n"
                   "Packs, recordings and settings are left untouched.\n\n"
                   "Continue?"),
    "upd_dl":     ("Lade ... %d%%", "Downloading ... %d%%"),
    "upd_check":  ("Prüfe das Archiv ...", "Checking the archive ..."),
    "upd_swap":   ("Tausche Dateien - gleich geht es weiter ...",
                   "Replacing files - back in a moment ..."),
    "upd_fail_t": ("Update fehlgeschlagen", "Update failed"),
    "upd_fail":   ("Es hat nicht geklappt:\n\n%s\n\n"
                   "Du kannst die Version auch von Hand von der "
                   "Release-Seite laden.",
                   "It did not work:\n\n%s\n\n"
                   "You can also download the version by hand from the "
                   "release page."),
}


def t(key, *args):
    pair = T.get(key)
    if not pair:
        return key
    val = pair[1] if LANG == "en" else pair[0]
    return val % args if args else val


def load_cfg():
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cfg(cfg):
    try:
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# ==========================================================================
#  Zeichen-Helfer / drawing helpers
# ==========================================================================

def lerp_color(c1, c2, f):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(
        int(a[i] + (b[i] - a[i]) * f) for i in range(3))


def round_rect(cv, x0, y0, x1, y1, r=14, **kw):
    r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
           x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return cv.create_polygon(pts, smooth=True, **kw)


class Button(object):
    """Selbstgezeichneter Knopf mit Hover- und Sperrzustand."""

    STYLES = {
        "primary": (ACC, ACC_HI, "#ffffff"),
        "record":  (RED, RED_HI, "#2b0710"),
        "go":      (TEAL, TEAL_HI, "#062a20"),
        "ghost":   (PANEL_HI, EDGE, TXT),
        "flat":    ("", "", DIM),
    }

    def __init__(self, cv, x, y, w, h, text, command, kind="ghost",
                 font=("Segoe UI Semibold", 11), radius=None):
        self.cv = cv
        self.box = (x, y, x + w, y + h)
        self.command = command
        self.kind = kind
        self.enabled = True
        self.hover = False
        r = radius if radius is not None else min(16, h / 2)
        if kind == "flat":
            self.rect = None
        else:
            self.rect = round_rect(cv, x, y, x + w, y + h, r=r,
                                   fill=self.STYLES[kind][0], outline="")
        self.label = cv.create_text(x + w / 2, y + h / 2, text=text,
                                    fill=self.STYLES[kind][2], font=font)
        self.refresh()

    def refresh(self):
        base, hi, fg = self.STYLES[self.kind]
        if not self.enabled:
            fill, txt = PANEL, "#565d7d"
        elif self.hover:
            fill, txt = (hi if self.kind != "flat" else "", TXT)
        else:
            fill, txt = base, fg
        if self.rect is not None:
            self.cv.itemconfigure(self.rect, fill=fill)
        self.cv.itemconfigure(self.label, fill=txt)

    def set_enabled(self, value):
        value = bool(value)
        if value != self.enabled:
            self.enabled = value
            self.refresh()

    def set_text(self, text):
        self.cv.itemconfigure(self.label, text=text)

    def hit(self, x, y):
        x0, y0, x1, y1 = self.box
        return x0 <= x <= x1 and y0 <= y <= y1

    def set_hover(self, value):
        if value != self.hover:
            self.hover = value
            self.refresh()


class Slider(object):
    """Selbstgezeichneter Schieberegler: Beschriftung, Spur, Prozentwert."""

    def __init__(self, cv, x, y, w, label, value, lo, hi, on_change):
        self.cv = cv
        self.lo, self.hi = lo, hi
        self.on_change = on_change
        self.label = cv.create_text(x, y, anchor="w", text=label, fill=DIM,
                                    font=("Segoe UI", 10))
        lx1 = cv.bbox(self.label)[2]
        self.x0, self.x1 = lx1 + 12, x + w - 46
        self.y = y
        self.box = (self.x0 - 8, y - 12, self.x1 + 8, y + 12)
        cv.create_line(self.x0, y, self.x1, y, fill=PANEL_HI, width=4,
                       capstyle="round")
        self.fill = cv.create_line(self.x0, y, self.x0, y, fill=ACC, width=4,
                                   capstyle="round")
        self.knob = cv.create_oval(0, 0, 0, 0, fill=TXT, outline="")
        self.text = cv.create_text(x + w, y, anchor="e", text="", fill=DIM,
                                   font=("Consolas", 10))
        self.set(value)

    def set(self, value):
        self.value = max(self.lo, min(self.hi, value))
        f = (self.value - self.lo) / float(self.hi - self.lo)
        kx = self.x0 + (self.x1 - self.x0) * f
        self.cv.coords(self.fill, self.x0, self.y, kx, self.y)
        self.cv.coords(self.knob, kx - 7, self.y - 7, kx + 7, self.y + 7)
        self.cv.itemconfigure(self.text, text="%d%%" % round(self.value * 100))

    def hit(self, x, y):
        x0, y0, x1, y1 = self.box
        return x0 <= x <= x1 and y0 <= y <= y1

    def drag(self, x):
        f = (x - self.x0) / float(max(1, self.x1 - self.x0))
        v = self.lo + max(0.0, min(1.0, f)) * (self.hi - self.lo)
        v = round(v / 0.05) * 0.05            # in 5-%-Schritten
        if abs(v - 1.0) < 0.04:
            v = 1.0                           # 100 % rastet ein
        if v != self.value:
            self.set(v)
            self.on_change(self.value)


# ==========================================================================
class NetSession(object):
    """Eine laufende Mehrspieler-Runde / one running multiplayer game."""

    def __init__(self, client, server=None, room=None):
        self.client = client
        self.server = server          # nur beim Host
        self.room = room              # nur beim Host
        self.tunnel = None
        self.tunnel_url = None
        self.state = None             # letzter Stand vom Host
        self.revs = {}                # Zeile -> Version der geholten Aufnahme
        self.unsent = {}              # Zeile -> "put" | "del", noch offen
        self.failed = set()           # gescheiterte Sendungen
        self.fetching = set()
        self.trouble = None           # Verbindung hakt gerade
        self.want_done = False        # "Bereit" gedrueckt, ggf. noch senden

    @property
    def is_host(self):
        return self.room is not None

    @property
    def me(self):
        return self.client.player

    def close(self):
        self.client.stop_polling()
        if self.is_host:
            self.server.close()
            net.stop_process(self.tunnel)
        else:
            self.client.leave()


# ==========================================================================
class Game(tk.Tk):

    def __init__(self):
        super().__init__()
        appwin.set_icon(self, "DubStage")
        self.cfg = load_cfg()
        # "mic" wurde frueher bei jedem Start ungefragt gespeichert (meist
        # einfach das erste Geraet). Ab jetzt zaehlt nur "mic_choice".
        self.cfg.pop("mic", None)
        set_lang(self.cfg.get("lang", "de"))
        self.title(t("title"))
        # Nicht groesser oeffnen als der Bildschirm hergibt - sonst liegt
        # die untere Knopfleiste hinter der Taskleiste.
        sh = self.winfo_screenheight()
        self.geometry("1200x%d" % min(900, max(780, sh - 130)))
        self.minsize(1020, 780)
        self.configure(bg=BG_BOT)

        self.msgq = queue.Queue()
        self.mic = ds.Mic(ds.SR)
        self.packs = []
        self.pack = None
        self.line_i = 0
        self.mix = None
        self.mix_parts = None         # (Stimmen, Hintergrund) im Mehrspieler
        self.screen = "menu"
        self.phase = "idle"           # idle | listen | record | play
        self._phase_deadline = None
        self.sel_pack = 0
        self.menu_scroll = 0
        self._scanned = False
        self._busy = False
        self._photo = None
        self._imgcache = {}
        self._frame_size = None
        self._last_idx = None
        self._play = None             # laufende Wiedergabe / running playback
        self._rec_guard = None
        self._rec_done = True
        self._resize_job = None
        self._embedded = []
        self.buttons = []
        self.chips = []
        self.sliders = []
        self._drag = None             # Regler, der gerade gezogen wird
        self._fit_cache = {}          # Text-Item -> (Text, Hoehe) schon eingepasst
        self._thumbs = {}             # Vorschaubilder im Menue / menu thumbnails
        self._thumb_jobs = set()
        self._thumb_redraw = False
        self._logo_img = None
        self._loading = False
        self._unpacking = 0           # Archive, die gerade entpackt werden
        self.net = None               # NetSession im Mehrspieler
        self.lobby_scroll = 0
        self.lobby_by_line = False
        self.lobby_rows = []

        self.upd_info = None          # gefundenes Release / found release
        self.upd_open = False         # Changelog aufgeklappt?
        self.upd_busy = False
        self.upd_dismissed = False
        self.upd_sub_item = None
        self.upd_scroll = 0           # Zeile oben im Changelog
        self.upd_maxscroll = 0
        self.upd_rect = None          # Flaeche des Changelog-Feldes

        self.cv = tk.Canvas(self, bg=BG_BOT, highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self.cv.bind("<Configure>", self._on_resize)
        self.cv.bind("<Motion>", self._on_motion)
        self.cv.bind("<Button-1>", self._on_click)
        self.cv.bind("<B1-Motion>", self._on_drag)
        self.cv.bind("<ButtonRelease-1>", self._on_release)
        self.cv.bind("<MouseWheel>", self._on_wheel)
        self.bind("<Escape>", lambda e: self._on_escape())
        self.bind("<space>", lambda e: self._on_space())

        self._style()
        self.after(50, self.show_menu)
        self.after(60, self._pump)
        self.after(1400, self._check_update)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _style(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except Exception:
            pass
        s.configure("Mic.TCombobox", fieldbackground=PANEL_HI,
                    background=PANEL_HI, foreground=TXT, arrowcolor=TXT,
                    bordercolor=EDGE, lightcolor=PANEL_HI, darkcolor=PANEL_HI,
                    selectbackground=PANEL_HI, selectforeground=TXT)
        # "readonly" hat eigene Farben, die configure() nicht erreicht
        s.map("Mic.TCombobox",
              fieldbackground=[("readonly", PANEL_HI), ("disabled", PANEL)],
              background=[("readonly", PANEL_HI), ("active", PANEL_HI)],
              foreground=[("readonly", TXT), ("disabled", DIM)],
              selectbackground=[("readonly", PANEL_HI), ("focus", PANEL_HI)],
              selectforeground=[("readonly", TXT), ("focus", TXT)],
              arrowcolor=[("readonly", TXT), ("disabled", DIM)])
        # Die aufklappende Liste ist ein Tk-Widget, das ttk nicht gestaltet
        self.option_add("*TCombobox*Listbox.background", PANEL_HI)
        self.option_add("*TCombobox*Listbox.foreground", TXT)
        self.option_add("*TCombobox*Listbox.selectBackground", ACC)
        self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        self.option_add("*TCombobox*Listbox.borderWidth", 0)

    # ------------------------------------------------------------- Basics
    def size(self):
        w = self.cv.winfo_width()
        h = self.cv.winfo_height()
        return (w if w > 300 else 1200), (h if h > 300 else 900)

    def _clear_canvas(self):
        for w in self._embedded:
            try:
                w.destroy()
            except Exception:
                pass
        self._embedded = []
        self.buttons = []
        self.chips = []
        self.sliders = []
        self._drag = None
        self._fit_cache = {}
        self.cv.delete("all")
        self._photo = None

    def _backdrop(self):
        w, h = self.size()
        steps = 46
        for i in range(steps):
            y0 = h * i / steps
            y1 = h * (i + 1) / steps + 1
            self.cv.create_rectangle(
                0, y0, w, y1, width=0,
                fill=lerp_color(BG_TOP, BG_BOT, i / float(steps - 1)))
        # weicher Lichtkegel oben mittig
        for i in range(9):
            f = i / 9.0
            rw = w * (0.18 + 0.42 * f)
            self.cv.create_oval(w / 2 - rw, -h * 0.42 + f * 40,
                                w / 2 + rw, h * (0.16 + 0.30 * f),
                                fill=lerp_color(BG_TOP, "#2a2f55", 0.5 - f * 0.5),
                                outline="")

    def _fit_text(self, item, text, max_h, size=16, min_size=10,
                  family="Segoe UI Semibold"):
        """
        Setzt den Text und verkleinert die Schrift, bis er in max_h passt.
        Reicht auch die kleinste nicht, wird er mit "…" gekuerzt.
        """
        cv = self.cv
        if self._fit_cache.get(item) == (text, max_h):
            return                       # unveraendert, nichts zu messen
        cv.itemconfigure(item, text=text)

        def fits():
            box = cv.bbox(item)
            return box is None or box[3] - box[1] <= max_h

        for s in range(size, min_size - 1, -1):
            cv.itemconfigure(item, font=(family, s))
            if fits():
                break
        else:
            words = text.split()
            while len(words) > 1 and not fits():
                words.pop()
                cv.itemconfigure(item, text=" ".join(words) + " …")
        self._fit_cache[item] = (text, max_h)

    def _clip_line(self, item, text, max_w):
        """Kuerzt einzeiligen Text mit "…", bis er in max_w passt."""
        cv = self.cv
        cv.itemconfigure(item, text=text)
        while len(text) > 1:
            x0, _y0, x1, _y1 = cv.bbox(item)
            if x1 - x0 <= max_w:
                break
            text = text[:-1]
            cv.itemconfigure(item, text=text.rstrip() + "…")

    def _btn(self, *a, **kw):
        b = Button(self.cv, *a, **kw)
        self.buttons.append(b)
        return b

    def _on_resize(self, _e=None):
        if self._resize_job:
            try:
                self.after_cancel(self._resize_job)
            except Exception:
                pass
        self._resize_job = self.after(140, self._rebuild)

    def _rebuild(self):
        self._resize_job = None
        if self.screen == "menu":
            self.show_menu()
        elif self.screen == "stage":
            self.build_stage()
        elif self.screen == "finale":
            self.build_finale()
        elif self.screen == "lobby":
            self.build_lobby()
        elif self.screen == "waiting":
            self.build_waiting()
        elif self.screen == "assembling":
            self.build_assembling()

    def _on_motion(self, e):
        for b in self.buttons:
            b.set_hover(b.enabled and b.hit(e.x, e.y))

    def _on_click(self, e):
        for s in self.sliders:
            if s.hit(e.x, e.y):
                self._drag = s
                s.drag(e.x)
                return
        for b in self.buttons:
            if b.enabled and b.hit(e.x, e.y):
                b.command()
                return
        if self.screen == "menu":
            for i, (x0, y0, x1, y1) in enumerate(self.chips):
                if x0 <= e.x <= x1 and y0 <= e.y <= y1:
                    self.sel_pack = self.menu_scroll + i
                    self.show_menu()
                    return
        elif self.screen == "stage" and self.phase == "idle":
            for i, (x0, y0, x1, y1) in enumerate(self.chips):
                if x0 <= e.x <= x1 and y0 - 8 <= e.y <= y1 + 8:
                    self.goto_line(i)
                    return
        elif self.screen == "lobby":
            for (x0, y0, x1, y1), files in self.lobby_rows:
                if x0 <= e.x <= x1 and y0 <= e.y <= y1:
                    self._lobby_cycle(files)
                    return

    def _on_drag(self, e):
        if self._drag is not None:
            self._drag.drag(e.x)

    def _on_release(self, _e):
        if self._drag is not None:
            self._drag = None
            save_cfg(self.cfg)

    # ---------------------------------------- Hintergrund-Regler (Mehrspieler)
    def _back_slider(self, right, y):
        """Lautstaerke des Hintergrunds, rechtsbuendig bis x=right."""
        if self.net is None:
            return None
        s = Slider(self.cv, right - 250, y, 250, t("bg_vol"),
                   self.mic.back_gain, 0.0, 1.5, self._set_back_gain)
        self.sliders.append(s)
        return s

    def _set_back_gain(self, value):
        self.mic.back_gain = value
        self.cfg["backing_vol"] = value

    def _play_backed(self, audio, start, level):
        """
        Wie mic.play(_with_backing(...)), im Mehrspieler aber mit getrenntem
        Hintergrund, damit der Regler live wirkt.
        """
        back = getattr(self.pack, "backing_audio", None)
        audio = np.asarray(audio, dtype=np.float32)
        if self.net is None or back is None or not len(audio):
            self.mic.play(self._with_backing(audio, start, level))
            return
        seg = ds.fit_len(ds.slice_audio(back, start, len(audio) / float(ds.SR)),
                         len(audio))
        self.mic.play_mix(*ds.mix_parts(audio * 0.95, seg * level, 0.95))

    def _on_wheel(self, e):
        if self.screen == "lobby":
            self.lobby_scroll = max(0, self.lobby_scroll
                                    + (-1 if e.delta > 0 else 1))
            self.build_lobby()
            return
        if self.screen != "menu":
            return
        step = -1 if e.delta > 0 else 1
        # Ueber dem Changelog blaettert das Rad im Changelog.
        r = self.upd_rect
        if r and r[0] <= e.x <= r[2] and r[1] <= e.y <= r[3]:
            new = max(0, min(self.upd_maxscroll, self.upd_scroll + step * 3))
            if new != self.upd_scroll:
                self.upd_scroll = new
                self.show_menu()
            return
        self.menu_scroll = max(0, self.menu_scroll - (1 if e.delta > 0 else -1))
        self.show_menu()

    def _on_escape(self):
        if self.screen == "stage":
            self.leave_round()
        elif self.screen == "finale" and not self.net:
            self.show_menu()
        elif self.screen in ("lobby", "waiting", "assembling", "finale"):
            self.leave_net()

    def _on_space(self):
        if self.screen == "stage" and self.phase == "idle":
            self.do_record()
        elif self.screen == "finale":
            self.toggle_finale_play()

    # ==================================================================
    #  MENUE
    # ==================================================================
    def show_menu(self):
        if self.net is not None:
            self._net_close()
        self.screen = "menu"
        self._set_phase("idle")
        self._stop_audio()
        if not self._scanned:
            self._scanned = True
            pending = []
            self.packs = ds.find_packs(
                extra_dirs=self.cfg.get("extra_dirs") or [], pending=pending)
            if pending:
                self.after(10, lambda: self._unpack_archives(pending))
            self.sel_pack = min(self.sel_pack, max(0, len(self.packs) - 1))
        self._clear_canvas()
        self._backdrop()
        w, h = self.size()
        cv = self.cv

        # Kopf: Symbol und Name als Gruppe mittig, darunter die Zeile.
        title = cv.create_text(0, 64, text="DubStage", fill=TXT, anchor="w",
                               font=("Segoe UI Black", 34))
        box = cv.bbox(title) or (0, 0, 220, 0)
        logo = self._logo()
        lw = 54 if logo else 0
        x0 = (w - (lw + (box[2] - box[0]))) / 2
        if logo:
            cv.create_image(x0, 64, image=logo, anchor="w")
        cv.coords(title, x0 + lw, 64)
        cv.create_text(w / 2, 112, text=t("tagline"), fill=DIM,
                       font=("Segoe UI", 12))

        # Sprachumschalter
        for i, (code, label) in enumerate((("de", "DE"), ("en", "EN"))):
            x = w - 120 + i * 52
            active = (LANG == code)
            round_rect(cv, x, 26, x + 46, 54, r=14,
                       fill=ACC if active else PANEL, outline="")
            cv.create_text(x + 23, 40, text=label,
                           fill="#ffffff" if active else DIM,
                           font=("Segoe UI Semibold", 10))
        self._btn(w - 120, 26, 46, 28, "", lambda: self._set_lang("de"), "flat")
        self._btn(w - 68, 26, 46, 28, "", lambda: self._set_lang("en"), "flat")

        off = self._draw_update_banner(cv, w, h)

        cv.create_text(70, 168 + off, text=t("pick"), fill=TXT, anchor="w",
                       font=("Segoe UI Semibold", 14))

        # ---- Pack-Karten
        list_x0, list_x1 = 70, w - 70
        card_h, gap = 86, 12
        top = 196 + off
        avail = h - top - 210
        per_page = max(1, int(avail // (card_h + gap)))
        self.menu_scroll = max(0, min(self.menu_scroll,
                                      max(0, len(self.packs) - per_page)))
        visible = self.packs[self.menu_scroll:self.menu_scroll + per_page]

        if not self.packs:
            round_rect(cv, list_x0, top, list_x1, top + 150, r=18,
                       fill=PANEL, outline=EDGE)
            cv.create_text((list_x0 + list_x1) / 2, top + 52,
                           text=t("no_packs"), fill=GOLD,
                           font=("Segoe UI Semibold", 14))
            cv.create_text((list_x0 + list_x1) / 2, top + 100,
                           text=t("no_packs_2"), fill=DIM,
                           font=("Segoe UI", 10), justify="center")
        for i, p in enumerate(visible):
            gi = self.menu_scroll + i
            y = top + i * (card_h + gap)
            sel = (gi == self.sel_pack)
            round_rect(cv, list_x0, y, list_x1, y + card_h, r=16,
                       fill=PANEL_HI if sel else PANEL,
                       outline=ACC if sel else EDGE)
            thumb = self._thumb(p, PANEL_HI if sel else PANEL)
            tx = list_x0 + 12
            if thumb:
                cv.create_image(tx, y + card_h / 2, image=thumb, anchor="w")
            else:
                round_rect(cv, tx, y + (card_h - THUMB_H) / 2, tx + THUMB_W,
                           y + (card_h + THUMB_H) / 2, r=10, fill=BG_BOT,
                           outline="")
                cv.create_text(tx + THUMB_W / 2, y + card_h / 2, text="▶",
                               fill=EDGE, font=("Segoe UI", 16))
            text_x = tx + THUMB_W + 18
            cv.create_text(text_x, y + 32, anchor="w", text=p.name,
                           fill=TXT if sel else "#c9cfe8",
                           font=("Segoe UI Semibold", 14))
            dur = ds.pack_duration(p)
            meta = "%s   ·   %s   ·   %s" % (
                t("lines_n", len(p.lines)), pc.fmt_time(dur)[:-4],
                t("with_back") if p.backing else t("no_back"))
            cv.create_text(text_x, y + 57, anchor="w", text=meta,
                           fill=DIM, font=("Segoe UI", 10))
            if sel:
                cv.create_text(list_x1 - 26, y + card_h / 2, anchor="e",
                               text="▶", fill=ACC,
                               font=("Segoe UI", 18))
            self.chips.append((list_x0, y, list_x1, y + card_h))

        if len(self.packs) > per_page:
            cv.create_text(w / 2, top + per_page * (card_h + gap) + 6,
                           text="%d / %d" % (self.menu_scroll + len(visible),
                                             len(self.packs)),
                           fill=DIM, font=("Segoe UI", 9))

        # ---- Mikrofonzeile
        my = h - 168
        round_rect(cv, 70, my, w - 70, my + 66, r=16, fill=PANEL, outline=EDGE)
        cv.create_text(96, my + 33, anchor="w", text=t("mic"), fill=DIM,
                       font=("Segoe UI Semibold", 11))
        if self.mic.available:
            devs = self.mic.devices()
            self.mic_default = t("mic_default",
                                 self.mic.default_name() or "?")
            names = [self.mic_default] + ["%d  %s" % (i, n) for i, n in devs]
            # Beim Neuzeichnen (Fenstergroesse, Vorschaubilder) die gerade
            # gewaehlte Quelle behalten. Sonst die zuletzt bewusst gewaehlte -
            # nach Namen, die Nummern koennen sich zwischen Starts aendern.
            old = getattr(self, "mic_var", None)
            keep = old.get() if old is not None else None
            if keep not in names:
                chosen = self.cfg.get("mic_choice") or ""
                keep = next((n for n in names[1:]
                             if n.split(None, 1)[-1] == chosen), None)
            self.mic_var = tk.StringVar(value=keep or self.mic_default)
            box = ttk.Combobox(self, textvariable=self.mic_var, width=44,
                               state="readonly", values=names,
                               style="Mic.TCombobox")
            box.bind("<<ComboboxSelected>>", self._mic_chosen)
            self._embedded.append(box)
            cv.create_window(200, my + 33, window=box, anchor="w")
            self._btn(w - 250, my + 17, 100, 32, t("mic_test"),
                      self.test_mic, "ghost")
            self.mic_msg = cv.create_text(w - 270, my + 33, anchor="e",
                                          text="", fill=DIM,
                                          font=("Segoe UI", 10))
        else:
            cv.create_text(200, my + 33, anchor="w", text=t("no_sd"),
                           fill=RED, font=("Segoe UI", 10))
            self.mic_msg = None

        # ---- untere Knopfleiste
        by = h - 78
        self._btn(70, by, 140, 44, t("rescan"), self.scan_packs, "ghost")
        self.b_add = self._btn(222, by, 176, 44, t("add_folder"),
                               self.add_folder, "ghost")
        start = self._btn(w - 250, by, 180, 44, t("start"), self.start_round,
                          "go", font=("Segoe UI Semibold", 13))
        playable = self.mic.available and HAVE_PIL
        start.set_enabled(bool(self.packs) and playable)
        host = self._btn(w - 412, by, 150, 44, t("host"), self.host_game,
                         "primary")
        host.set_enabled(bool(self.packs) and playable)
        join = self._btn(w - 574, by, 150, 44, t("join"), self.join_game,
                         "ghost")
        join.set_enabled(playable)
        self.status_item = cv.create_text(w / 2, by - 14, text="", fill=DIM,
                                          font=("Segoe UI", 10))
        if self._unpacking:
            cv.itemconfigure(self.status_item, fill=GOLD,
                             text=t("unpacking", self._unpacking))

    # ==================================================================
    #  UPDATE
    # ==================================================================
    def _draw_update_banner(self, cv, w, h):
        """Banner im Menue. Gibt zurueck, um wieviel alles darunter rutscht."""
        info = self.upd_info
        self.upd_rect = None
        self.upd_sub_item = None
        if not info or self.upd_dismissed:
            return 0

        x0, x1 = 70, w - 70
        y0 = 140
        strip = 62
        notes_h = 0
        if self.upd_open:
            # nie so hoch, dass von der Packliste nichts mehr uebrig bleibt
            notes_h = max(70, min(190, h - 560))
        bh = strip + (notes_h + 12 if self.upd_open else 0)

        round_rect(cv, x0, y0, x1, y0 + bh, r=16, fill=BAN, outline=ACC)
        cv.create_text(x0 + 24, y0 + 22, anchor="w",
                       text=t("upd_head", info.get("version", "?")),
                       fill="#ffffff", font=("Segoe UI Semibold", 13))
        self.upd_sub_item = cv.create_text(
            x0 + 24, y0 + 44, anchor="w",
            text=t("upd_sub", upd.VERSION), fill="#b6b1dc",
            font=("Segoe UI", 10))

        # Knoepfe von rechts nach links
        bx = x1 - 22
        for label, cmd, style, bw in (
                (t("upd_later"), self._hide_banner, "flat", 92),
                (t("upd_now"), self._do_update, "go", 150),
                (t("upd_less") if self.upd_open else t("upd_more"),
                 self._toggle_notes, "ghost", 140)):
            bx -= bw
            b = self._btn(bx, y0 + 15, bw, 32, label, cmd, style)
            if style == "go" and self.upd_busy:
                b.set_enabled(False)
            bx -= 8

        self.upd_rect = None
        if self.upd_open:
            ny = y0 + strip
            round_rect(cv, x0 + 16, ny, x1 - 16, ny + notes_h, r=12,
                       fill=BAN_TXT, outline="")
            text = upd.plain_notes(info.get("notes")) or t("upd_nonotes")
            # Der Canvas bricht selbst um, blaettern muessen wir selbst.
            cols = max(20, int((x1 - x0 - 68) / 6.9))
            rows = max(3, int((notes_h - 18) / 17))
            lines = []
            for para in text.split("\n"):
                lines.extend(textwrap.wrap(para, cols) or [""])

            top_line = max(0, min(self.upd_scroll, max(0, len(lines) - rows)))
            self.upd_scroll = top_line
            self.upd_rect = (x0 + 16, ny, x1 - 16, ny + notes_h)
            self.upd_maxscroll = max(0, len(lines) - rows)

            cv.create_text(x0 + 32, ny + 10, anchor="nw",
                           text="\n".join(lines[top_line:top_line + rows]),
                           fill="#ded9ff", font=("Segoe UI", 10),
                           justify="left", width=x1 - x0 - 64)
            if self.upd_maxscroll:
                cv.create_text(x1 - 30, ny + notes_h - 12, anchor="se",
                               text="%d / %d  -  Mausrad"
                                    % (top_line + rows, len(lines)),
                               fill="#8c86bb", font=("Segoe UI", 8))
        return bh + 16

    def _check_update(self):
        cache = self.cfg.get("upd_cache") or {}
        if cache.get("tag") and upd.is_newer(cache["tag"]):
            self.upd_info = cache
            if self.screen == "menu":
                self.show_menu()
        if not upd.due(self.cfg):
            return

        def work():
            try:
                info = upd.check_latest()
            except Exception:
                return                      # kein Netz, kein Drama
            self.msgq.put(("update", info))

        threading.Thread(target=work, daemon=True).start()

    def _toggle_notes(self):
        self.upd_open = not self.upd_open
        self.show_menu()

    def _hide_banner(self):
        self.upd_dismissed = True
        self.show_menu()

    def _upd_say(self, text):
        if self.upd_sub_item is None:
            return
        try:
            self.cv.itemconfigure(self.upd_sub_item, text=text, fill=GOLD)
        except Exception:
            pass

    def _do_update(self):
        info = self.upd_info
        if not info or self.upd_busy:
            return
        if not info.get("zip"):
            webbrowser.open(info.get("page") or upd.RELEASES_PAGE)
            return
        if not messagebox.askyesno(t("upd_ask_t"),
                                   t("upd_ask", info.get("tag", "?"))):
            return

        self.upd_busy = True
        self.show_menu()
        self._upd_say(t("upd_dl", 0))

        def work():
            wd = tempfile.mkdtemp(prefix="dubstage_upd_")
            try:
                zp = os.path.join(wd, "release.zip")

                def prog(done, total):
                    pct = int(done * 100 / total) if total else 0
                    self.msgq.put(("upd_say", t("upd_dl", pct)))

                upd.download_zip(info["zip"], zp, progress=prog)
                self.msgq.put(("upd_say", t("upd_check")))
                root = upd.stage(zp, os.path.join(wd, "neu"))
                self.msgq.put(("upd_say", t("upd_swap")))
                upd.apply(root, APP_DIR, which="DubStage",
                          tag=info.get("tag", ""))
                self.msgq.put(("upd_quit", None))
            except Exception as e:
                self.msgq.put(("upd_error", "%s" % e))

        threading.Thread(target=work, daemon=True).start()

    def _set_lang(self, code):
        if code == LANG:
            return
        set_lang(code)
        self.cfg["lang"] = LANG
        save_cfg(self.cfg)
        self.show_menu()

    def scan_packs(self):
        self._scanned = False
        self._thumbs = {}
        self._thumb_jobs = set()
        self.show_menu()

    # ------------------------------------------------------ Bilder im Menue
    def _logo(self):
        if self._logo_img is None:
            self._logo_img = False
            if HAVE_PIL:
                try:
                    im = Image.open(os.path.join(APP_DIR, "assets",
                                                 "dubstage.png"))
                    im = im.convert("RGBA").resize((44, 44), Image.LANCZOS)
                    self._logo_img = ImageTk.PhotoImage(im)
                except Exception:
                    pass
        return self._logo_img or None

    def _thumb(self, pack, bg):
        """Vorschaubild mit runden Ecken auf der Kartenfarbe, oder None."""
        if not HAVE_PIL:
            return None
        key = (pack.folder, bg)
        if key in self._thumbs:
            return self._thumbs[key]
        path = ds.thumb_path(pack)
        fresh = False
        try:
            fresh = os.path.getmtime(path) >= os.path.getmtime(pack.video)
        except OSError:
            pass
        if not fresh:
            # Erzeugen dauert einen Moment - im Hintergrund, dann neu zeichnen.
            if pack.folder not in self._thumb_jobs:
                self._thumb_jobs.add(pack.folder)

                def work(p=pack):
                    ds.make_thumb(p)
                    self.msgq.put(("thumb", None))
                threading.Thread(target=work, daemon=True).start()
            return None
        try:
            from PIL import ImageDraw, ImageOps
            im = ImageOps.fit(Image.open(path).convert("RGB"),
                              (THUMB_W, THUMB_H), Image.LANCZOS)
            k = 4                                  # Kanten glaetten
            mask = Image.new("L", (THUMB_W * k, THUMB_H * k), 0)
            ImageDraw.Draw(mask).rounded_rectangle(
                (0, 0, THUMB_W * k - 1, THUMB_H * k - 1), radius=10 * k,
                fill=255)
            mask = mask.resize((THUMB_W, THUMB_H), Image.LANCZOS)
            out = Image.new("RGB", (THUMB_W, THUMB_H), bg)
            out.paste(im, (0, 0), mask)
            photo = ImageTk.PhotoImage(out)
        except Exception:
            photo = None
        self._thumbs[key] = photo
        return photo

    def add_folder(self):
        """Kleines Menue: Ordner mit Packs oder ein Zip/RAR."""
        m = tk.Menu(self, tearoff=0, bg=PANEL_HI, fg=TXT, bd=0,
                    activebackground=ACC, activeforeground="#ffffff",
                    font=("Segoe UI", 10))
        m.add_command(label=t("add_dir"), command=self._add_dir)
        m.add_command(label=t("add_archive"), command=self._add_archive)
        x0, y0, _x1, _y1 = self.b_add.box
        try:
            m.tk_popup(self.cv.winfo_rootx() + int(x0),
                       self.cv.winfo_rooty() + int(y0) - 58)
        finally:
            m.grab_release()

    def _add_source(self, path):
        extra = self.cfg.get("extra_dirs") or []
        if path not in extra:
            extra.append(path)
        self.cfg["extra_dirs"] = extra
        save_cfg(self.cfg)
        self._scanned = False
        self.show_menu()

    def _add_dir(self):
        d = filedialog.askdirectory(title=t("add_dir"))
        if d:
            self._add_source(d)

    def _add_archive(self):
        f = filedialog.askopenfilename(
            title=t("add_archive"),
            filetypes=[("Zip / RAR", "*.zip *.rar"), ("*", "*.*")])
        if f:
            self._add_source(f)

    def _unpack_archives(self, paths):
        """Zips/RARs im Hintergrund pruefen und entpacken, dann neu suchen."""
        if self._unpacking:
            return
        self._unpacking = len(paths)
        if self.screen == "menu":
            self.cv.itemconfigure(self.status_item, fill=GOLD,
                                  text=t("unpacking", len(paths)))
        result = {"new": 0, "failed": [], "empty": []}

        def work():
            for p in paths:
                target = ds.archive_target(p)
                if not ds.archive_has_pack(p):
                    ds.NOT_PACKS.add(target)
                    result["empty"].append(p)
                    continue
                try:
                    ds.extract_archive(p)
                    result["new"] += 1
                except Exception as ex:
                    traceback.print_exc()
                    ds.NOT_PACKS.add(target)     # nicht bei jedem Menue erneut
                    result["failed"].append("%s: %s" % (
                        os.path.basename(p), str(ex).strip()[:200]))

        def done():
            self._unpacking = 0
            chosen = [os.path.normpath(x)
                      for x in self.cfg.get("extra_dirs") or []]
            # Nur selbst gewaehlte Archive ohne Pack melden - fremde Zips in
            # einem Ordner (Downloads) gehen uns nichts an.
            empty = [os.path.basename(p) for p in result["empty"]
                     if os.path.normpath(p) in chosen]
            if self.screen == "menu":
                self._scanned = not result["new"]
                self.show_menu()
            elif result["new"]:
                self._scanned = False
            if result["failed"]:
                messagebox.showwarning(t("title"), t(
                    "unpack_fail", "\n".join(result["failed"])))
            if empty:
                messagebox.showinfo(t("title"),
                                    t("no_pack_in", "\n".join(empty)))
        self._run_bg(work, done)

    def test_mic(self):
        if not self.mic.available or self._busy:
            return
        self._busy = True
        if self.mic_msg:
            self.cv.itemconfigure(self.mic_msg, text=t("mic_run"), fill=GOLD)
        try:
            self.mic.start(device=self._mic_device())
        except Exception as ex:
            self._busy = False
            messagebox.showerror(t("err"), str(ex))
            return
        self.after(2200, self._finish_mic_test)

    def _finish_mic_test(self):
        data = self.mic.stop()
        self._busy = False
        lvl = ds.rms_db(data)
        if self.mic_msg is None:
            return
        if not len(data) or lvl < -70:
            self.cv.itemconfigure(self.mic_msg, text=t("mic_none"), fill=RED)
        elif lvl < -40:
            self.cv.itemconfigure(self.mic_msg, text=t("mic_low", lvl),
                                  fill=GOLD)
        else:
            self.cv.itemconfigure(self.mic_msg, text=t("mic_ok", lvl),
                                  fill=TEAL)
            self.mic.play(ds.normalize(data, 0.9))

    def _mic_chosen(self, _e=None):
        """Nur eine bewusste Auswahl wird gemerkt; Standard = leer."""
        val = self.mic_var.get()
        self.cfg["mic_choice"] = ("" if val == getattr(self, "mic_default",
                                                       None)
                                  else val.split(None, 1)[-1])
        save_cfg(self.cfg)

    def _mic_device(self):
        """None = Standard-Mikrofon von Windows."""
        try:
            return int(self.mic_var.get().split()[0])
        except Exception:
            return None

    # ==================================================================
    #  RUNDE VORBEREITEN
    # ==================================================================
    def start_round(self):
        if not self.packs:
            return
        if not self.mic.available:
            messagebox.showerror(t("err"), t("no_sd"))
            return
        if not HAVE_PIL:
            messagebox.showerror(t("err"), t("no_pil"))
            return
        self.pack = self.packs[self.sel_pack]
        self.cv.itemconfigure(self.status_item, text=t("loading"), fill=GOLD)
        for b in self.buttons:
            b.set_enabled(False)
        self._loading = True          # kein Neuzeichnen des Menues dazwischen
        self.update_idletasks()

        pack = self.pack

        def work():
            self._prepare_pack(pack)

        def done():
            self._loading = False
            self._use_pack(pack)
            self.build_stage()
        self._run_bg(work, done)

    def _prepare_pack(self, pack):
        """Laeuft im Hintergrund: Ton laden, Einzelbilder erzeugen."""
        fps = int(self.cfg.get("video_fps") or ds.FRAME_FPS)
        ds.load_pack_audio(pack)
        ds.extract_frames(pack, fps=max(8, min(30, fps)))

    def _use_pack(self, pack):
        self.pack = pack
        for l in pack.lines:
            l.take = None
        self.line_i = 0
        self._imgcache = {}
        self._probe_frame_size()

    # ==================================================================
    #  BUEHNE
    # ==================================================================
    def build_stage(self):
        self.screen = "stage"
        self._clear_canvas()
        self._backdrop()
        cv = self.cv
        w, h = self.size()
        pad = 34

        # Kopfzeile
        self._btn(pad, 24, 110, 38,
                  "‹  " + (t("net_leave") if self.net else t("menu")),
                  self.leave_round, "flat", font=("Segoe UI", 11))
        if self.net and self.net.is_host:
            self._btn(pad + 120, 24, 110, 38, t("lobby"),
                      self.net.room.back_to_lobby, "flat",
                      font=("Segoe UI", 11))
        title = cv.create_text(w / 2, 43, text=self.pack.name, fill=TXT,
                               font=("Segoe UI Semibold", 15))
        self.hdr_count = cv.create_text(w - pad, 43, anchor="e", text="",
                                        fill=DIM,
                                        font=("Segoe UI Semibold", 12))
        if self._back_slider(w - pad - 120, 43):
            # Titel darf weder Knoepfe links noch den Regler rechts beruehren
            left = pad + (240 if self.net.is_host else 120)
            self._clip_line(title, self.pack.name,
                            2 * min(w / 2 - left, w - pad - 390 - w / 2) - 24)

        # Videoflaeche
        top = 82
        bottom_needed = 382          # Leiste, Untertitel, Vergleich, Knoepfe
        vw, vh = self._video_size(w, h - top - bottom_needed, pad)
        vx = (w - vw) / 2
        vy = top
        self.video_box = (vx, vy, vw, vh)
        self._last_idx = None
        round_rect(cv, vx - 8, vy - 8, vx + vw + 8, vy + vh + 8, r=18,
                   fill="#05060a", outline=EDGE)
        self.video_item = cv.create_image(vx + vw / 2, vy + vh / 2,
                                          anchor="center")
        self.overlay_rect = round_rect(cv, vx, vy, vx + vw, vy + vh, r=12,
                                       fill="#000000", stipple="gray50",
                                       outline="", state="hidden")
        self.overlay_text = cv.create_text(vx + vw / 2, vy + vh / 2, text="",
                                           fill=GOLD,
                                           font=("Segoe UI Black", 68),
                                           state="hidden")

        # Zeitleiste der Zeilen
        ty = vy + vh + 18
        self.timeline_y = ty
        self._build_timeline(vx, vw, ty)

        # Untertitel - das, was gesprochen werden soll
        cy = ty + 28
        self.caption_h = 46          # bis knapp ueber den Zeilennamen
        self.caption_item = cv.create_text(
            vx + vw / 2, cy, anchor="n", text="", fill=GOLD,
            font=("Segoe UI Semibold", 16), width=vw - 40, justify="center")

        # Zeilenname und Zeitbereich, klein darunter
        ny = cy + 54
        self.line_title = cv.create_text(vx, ny, anchor="w", text="", fill=DIM,
                                         font=("Segoe UI", 10))
        self.line_time = cv.create_text(vx + vw, ny, anchor="e", text="",
                                        fill=DIM, font=("Consolas", 10))

        # Vergleichsstreifen: Original als Silhouette, Aufnahme darueber
        sy = ny + 16
        sh = 78
        self.strip_box = (vx, sy, vw, sh)
        round_rect(cv, vx, sy, vx + vw, sy + sh, r=10, fill="#11141f",
                   outline=EDGE)
        cv.create_line(vx + 10, sy + sh / 2, vx + vw - 10, sy + sh / 2,
                       fill="#252b47")
        self.strip_orig = cv.create_polygon(0, 0, 0, 0, 0, 0, fill=WAVE_ORIG,
                                            outline="", state="hidden")
        self.strip_take = cv.create_polygon(0, 0, 0, 0, 0, 0, fill=TEAL,
                                            outline="", stipple="gray50",
                                            state="hidden")
        self.strip_head = cv.create_line(0, 0, 0, 0, fill=GOLD, width=1,
                                         state="hidden")
        self.strip_msg = cv.create_text(vx + vw / 2, sy + sh / 2, text="",
                                        fill=DIM, font=("Segoe UI", 10))
        cv.create_text(vx + 12, sy + 12, anchor="w", text=t("legend_orig"),
                       fill=WAVE_ORIG_TXT, font=("Segoe UI Semibold", 9))
        self.legend_take = cv.create_text(vx + vw - 12, sy + 12, anchor="e",
                                          text=t("legend_take"), fill=TEAL,
                                          font=("Segoe UI Semibold", 9))
        self.strip_info = cv.create_text(vx + vw - 12, sy + sh - 12,
                                         anchor="e", text="", fill=DIM,
                                         font=("Segoe UI", 9))

        # Knopfreihe
        by = sy + sh + 20
        bw, bh = 190, 52
        gapx = 16
        total = bw * 3 + gapx * 2
        bx = (w - total) / 2
        self.b_orig = self._btn(bx, by, bw, bh, "▶  " + t("play_orig"),
                                self.play_original, "ghost",
                                font=("Segoe UI Semibold", 12))
        self.b_rec = self._btn(bx + bw + gapx, by, bw, bh,
                               "●  " + t("rec"), self.do_record, "record",
                               font=("Segoe UI Semibold", 13))
        self.b_take = self._btn(bx + 2 * (bw + gapx), by, bw, bh,
                                "▶  " + t("play_take"), self.play_take,
                                "ghost", font=("Segoe UI Semibold", 12))

        # Navigationsreihe
        ny2 = by + bh + 18
        self.b_prev = self._btn(bx, ny2, 130, 42, "‹  " + t("prev"),
                                self.prev_line, "ghost",
                                font=("Segoe UI", 11))
        self.b_skip = self._btn(bx + 146, ny2, 200, 42, t("skip"),
                                self.clear_take, "ghost",
                                font=("Segoe UI", 11))
        self.b_next = self._btn(bx + total - 170, ny2, 170, 42,
                                t("next") + "  ›", self.next_line,
                                "primary", font=("Segoe UI Semibold", 12))

        self.hint_item = cv.create_text(w / 2, ny2 + 62, text=t("hint"),
                                        fill=DIM, font=("Segoe UI", 10))
        self.sync()

    def _build_timeline(self, vx, vw, ty):
        cv = self.cv
        n = max(1, len(self.pack.lines))
        gap = 4 if n <= 60 else 2
        cw = max(3.0, (vw - gap * (n - 1)) / float(n))
        self.chips = []
        self.chip_items = []
        for i in range(n):
            x0 = vx + i * (cw + gap)
            item = round_rect(cv, x0, ty, x0 + cw, ty + 10,
                              r=min(5, cw / 2), fill=PANEL_HI, outline="")
            self.chip_items.append(item)
            self.chips.append((x0, ty, x0 + cw, ty + 10))

    # ---------------------------------------------------- Zustand anzeigen
    def current_line(self):
        if not self.pack or not (0 <= self.line_i < len(self.pack.lines)):
            return None
        return self.pack.lines[self.line_i]

    def sync(self):
        """Setzt Beschriftungen und Knopfzustaende passend zur Lage."""
        if self.screen != "stage":
            return
        line = self.current_line()
        n = len(self.pack.lines)
        busy = self.phase != "idle"
        has_take = line is not None and line.take is not None and len(line.take)
        mine = self._net_mine(line)
        if self.net:
            last = self._own_step(1) is None
            has_prev = self._own_step(-1) is not None
        else:
            last = self.line_i >= n - 1
            has_prev = self.line_i > 0

        # --- Knopfzustaende zuerst: die duerfen nie von der Anzeige abhaengen.
        # Aufnehmen ist auf jeder Zeile moeglich, auch auf der letzten.
        self.b_orig.set_enabled(not busy)
        self.b_rec.set_enabled(not busy and line is not None and mine)
        self.b_rec.set_text("●  " + (t("rec_again") if has_take else t("rec")))
        self.b_take.set_enabled(not busy and bool(has_take))
        self.b_take.set_text("▶  " + (t("play_take") if mine
                                      else t("their_take")))
        self.b_prev.set_enabled(not busy and has_prev)
        self.b_skip.set_enabled(not busy and bool(has_take) and mine)
        self.b_next.set_enabled(not busy)
        if last and self.net:
            self.b_next.set_text(t("ready_btn"))
        else:
            self.b_next.set_text((t("finish") if last else t("next")) + "  ›")

        # --- ab hier nur noch Kosmetik
        try:
            self.cv.itemconfigure(self.hdr_count,
                                  text=t("line_of", self.line_i + 1, n))
            if line is not None:
                self.cv.itemconfigure(self.line_title, text=line.name,
                                      fill=DIM)
                if self.net:
                    p = self._net_player(self._net_owner(line)) or \
                        {"name": t("role_free")}
                    self.cv.itemconfigure(
                        self.line_title, fill=p.get("color", DIM),
                        text="%s   ·   %s" % (
                            line.name, t("voiced_by", p.get("name", "?"))))
                    self.cv.itemconfigure(
                        self.legend_take,
                        text=t("legend_take") if mine
                        else t("legend_their", p.get("name", "?")))
                self.cv.itemconfigure(
                    self.line_time,
                    text="%s  –  %s" % (pc.fmt_time(line.start)[:-2],
                                        pc.fmt_time(line.end)[:-2]))
                self.cv.itemconfigure(self.caption_item,
                                      fill=GOLD if line.caption else DIM)
                self._fit_text(self.caption_item, line.caption or "",
                               self.caption_h)
            for i, l in enumerate(self.pack.lines):
                if i >= len(self.chip_items):
                    break
                recorded = l.take is not None and len(l.take)
                if i == self.line_i:
                    col = GOLD
                elif self.net:
                    p = self._net_player(self._net_owner(l)) or {}
                    owner_col = p.get("color", TEAL)
                    col = (owner_col if recorded
                           else lerp_color(PANEL_HI, owner_col, 0.3))
                elif recorded:
                    col = TEAL
                else:
                    col = PANEL_HI
                self.cv.itemconfigure(self.chip_items[i], fill=col)
            done = sum(1 for l in self.pack.lines
                       if l.take is not None and len(l.take))
            if self.net:
                hint = self._net_hint()
            else:
                hint = t("recorded_n", done, n) if done else t("hint")
            self.cv.itemconfigure(self.hint_item, text=hint)
            self._refresh_strip()
            if not busy and line is not None:
                self.show_frame(line.start)
        except Exception:
            traceback.print_exc()

    # ------------------------------------------- Vergleichsstreifen zeichnen
    STRIP_COLS = 320          # Aufloesung der Silhouetten

    def _strip_span(self, line):
        """Zeitachse des Streifens: Cliplaenge plus Nachlauf der Aufnahme."""
        return max(0.3, line.duration + TAIL)

    def _strip_geo(self):
        x0, y0, sw, sh = self.strip_box
        return (x0 + 12, sw - 24, y0 + sh / 2.0, sh / 2.0 - 16)

    def _polygon(self, xs, tops, bots):
        """Punkteliste fuer eine gefuellte Silhouette."""
        pts = []
        for x, y in zip(xs, tops):
            pts += [x, y]
        for x, y in zip(reversed(xs), reversed(bots)):
            pts += [x, y]
        return pts

    def _draw_strip_original(self):
        """Silhouette des Originalclips - Grundlage fuer den Vergleich."""
        cv = self.cv
        line = self.current_line()
        if line is None or line.audio is None or not len(line.audio):
            cv.itemconfigure(self.strip_orig, state="hidden")
            return
        left, width, mid, amp = self._strip_geo()
        span = self._strip_span(line)
        cols = self.STRIP_COLS
        n = max(4, int(cols * min(1.0, line.duration / span)))
        peaks = pc.waveform_peaks(line.audio, n)
        if not peaks:
            cv.itemconfigure(self.strip_orig, state="hidden")
            return
        m = max(1e-6, max(max(abs(a), abs(b)) for a, b in peaks))
        xs, tops, bots = [], [], []
        for i, (lo, hi) in enumerate(peaks):
            xs.append(left + width * (i / float(cols)))
            tops.append(mid - (hi / m) * amp)
            bots.append(mid - (lo / m) * amp)
        cv.coords(self.strip_orig, *self._polygon(xs, tops, bots))
        cv.itemconfigure(self.strip_orig, state="normal")

    def _draw_strip_take(self, live=False):
        """Aufnahme darueber - waehrend der Aufnahme live mitwachsend."""
        cv = self.cv
        line = self.current_line()
        if line is None:
            cv.itemconfigure(self.strip_take, state="hidden")
            return
        left, width, mid, amp = self._strip_geo()
        span = self._strip_span(line)
        cols = self.STRIP_COLS
        xs, tops, bots = [], [], []

        if live:
            env, step = self.mic.envelope()
            if not env:
                cv.itemconfigure(self.strip_take, state="hidden")
                return
            m = max(1e-4, max(env))
            done = len(env) * step
            n = max(2, int(cols * min(1.0, done / span)))
            for i in range(n):
                sec = span * (i / float(cols))
                k = int(sec / step)
                v = (env[k] / m) if k < len(env) else 0.0
                xs.append(left + width * (i / float(cols)))
                tops.append(mid - v * amp)
                bots.append(mid + v * amp)
        else:
            take = line.take
            if take is None or not len(take):
                cv.itemconfigure(self.strip_take, state="hidden")
                return
            dur = len(take) / float(ds.SR)
            n = max(4, int(cols * min(1.0, dur / span)))
            peaks = pc.waveform_peaks(take, n)
            if not peaks:
                cv.itemconfigure(self.strip_take, state="hidden")
                return
            m = max(1e-6, max(max(abs(a), abs(b)) for a, b in peaks))
            for i, (lo, hi) in enumerate(peaks):
                xs.append(left + width * (i / float(cols)))
                tops.append(mid - (hi / m) * amp)
                bots.append(mid - (lo / m) * amp)

        if len(xs) < 2:
            cv.itemconfigure(self.strip_take, state="hidden")
            return
        cv.coords(self.strip_take, *self._polygon(xs, tops, bots))
        cv.itemconfigure(self.strip_take, state="normal",
                         fill=RED if live else TEAL)
        cv.itemconfigure(self.legend_take, fill=RED if live else TEAL)

    def _strip_head(self, seconds=None):
        """Senkrechte Marke fuer die aktuelle Stelle."""
        line = self.current_line()
        if seconds is None or line is None:
            self.cv.itemconfigure(self.strip_head, state="hidden")
            return
        left, width, mid, amp = self._strip_geo()
        x0, y0, sw, sh = self.strip_box
        f = max(0.0, min(1.0, seconds / self._strip_span(line)))
        x = left + width * f
        self.cv.coords(self.strip_head, x, y0 + 6, x, y0 + sh - 6)
        self.cv.itemconfigure(self.strip_head, state="normal")

    def _refresh_strip(self):
        """Beschriftung und beide Silhouetten neu setzen."""
        cv = self.cv
        line = self.current_line()
        recording = (self.phase == "record")
        self._draw_strip_original()
        self._draw_strip_take(live=recording)
        if not recording:
            self._strip_head(None)

        if line is None:
            cv.itemconfigure(self.strip_msg, text="", fill=DIM)
            cv.itemconfigure(self.strip_info, text="")
            return
        if recording:
            cv.itemconfigure(self.strip_msg, text="", fill=RED)
            cv.itemconfigure(self.strip_info, text=t("recording"), fill=RED)
            return
        has = line.take is not None and len(line.take)
        cv.itemconfigure(self.strip_msg,
                         text="" if has else t("no_take"), fill=DIM)
        if has:
            lvl = ds.rms_db(line.take)
            info = t("take_len", len(line.take) / float(ds.SR))
            if lvl < -40:
                info += "   -   " + t("quiet_hint")
            cv.itemconfigure(self.strip_info, text=info,
                             fill=GOLD if lvl < -40 else DIM)
        else:
            cv.itemconfigure(self.strip_info, text="")

    # ------------------------------------------------------------- Video
    def show_frame(self, seconds):
        """Zeigt das Bild zum Zeitpunkt an."""
        if self.pack:
            self._show_index(ds.frame_at(self.pack, seconds))

    def _show_index(self, idx):
        """
        Zeigt ein bestimmtes Einzelbild. Wirft nie eine Ausnahme:
        ein Anzeigefehler darf den Ablauf niemals einfrieren.
        """
        try:
            if idx is None or not HAVE_PIL or not self.pack \
                    or not self.pack.frames:
                return
            if idx == self._last_idx:
                return                      # gleiches Bild, nichts zu tun
            photo = self._frame_photo(idx)
            if photo is not None:
                self._photo = photo
                self._last_idx = idx
                self.cv.itemconfigure(self.video_item, image=photo)
        except Exception:
            traceback.print_exc()

    def _frame_photo(self, idx):
        vx, vy, vw, vh = self.video_box
        key = (idx, int(vw), int(vh))
        photo = self._imgcache.get(key)
        if photo is not None:
            return photo
        try:
            im = Image.open(self.pack.frames[idx]).convert("RGB")
            iw, ih = im.size
            s = min(vw / float(iw), vh / float(ih), 1.0)   # nie vergroessern
            target = (max(1, int(iw * s)), max(1, int(ih * s)))
            if target != im.size:
                im = im.resize(target, Image.BILINEAR)
            photo = ImageTk.PhotoImage(im)
        except Exception:
            return None
        # aelteste Eintraege verwerfen statt alles auf einmal
        while len(self._imgcache) >= 48:
            self._imgcache.pop(next(iter(self._imgcache)))
        self._imgcache[key] = photo
        return photo

    def _video_size(self, win_w, avail_h, pad):
        """
        Bildflaeche im Seitenverhaeltnis der Einzelbilder und nie breiter
        als diese - so entfaellt jedes Hochskalieren.
        """
        fw, fh = self._frame_size or (ds.FRAME_W, int(ds.FRAME_W * 9 / 16))
        aspect = fw / float(max(1, fh))
        vw = int(min(fw, win_w - 2 * pad, max(120, avail_h) * aspect))
        vw = max(320, vw)
        return vw, int(round(vw / aspect))

    def _probe_frame_size(self):
        """Native Groesse der Einzelbilder, damit nie hochskaliert wird."""
        self._frame_size = None
        self._last_idx = None
        if HAVE_PIL and self.pack and self.pack.frames:
            try:
                with Image.open(self.pack.frames[0]) as im:
                    self._frame_size = im.size
            except Exception:
                traceback.print_exc()

    def _overlay(self, text=None, colour=GOLD, size=68):
        """
        Einblendung ueber dem Video. Grosse Schrift (Countdown) als Plakette
        in der Mitte; kleine (Aufnahme laeuft) als "REC"-Pille oben links -
        die Mitte des Bildes muss frei bleiben, man spricht ja lippensynchron.
        """
        cv = self.cv
        cv.delete("overlay")
        for item in (self.overlay_rect, self.overlay_text):
            cv.itemconfigure(item, state="hidden")
        if text is None:
            return
        vx, vy, vw, vh = self.video_box
        if size >= 40:
            tid = cv.create_text(vx + vw / 2, vy + vh / 2, text=text,
                                 fill=colour, font=("Segoe UI Black", size),
                                 tags="overlay")
            x0, y0, x1, y1 = cv.bbox(tid)
            side = max(x1 - x0, y1 - y0) + 44
            cx, cy = vx + vw / 2, vy + vh / 2
            badge = round_rect(cv, cx - side / 2, cy - side / 2,
                               cx + side / 2, cy + side / 2, r=28,
                               fill="#0b0d16", outline=colour, width=2,
                               tags="overlay")
        else:
            tid = cv.create_text(vx + 38, vy + 30, anchor="w",
                                 text=text.upper(), fill=colour,
                                 font=("Segoe UI Semibold", 11),
                                 tags="overlay")
            x0, y0, x1, y1 = cv.bbox(tid)
            badge = round_rect(cv, vx + 14, vy + 14, x1 + 14, vy + 46, r=16,
                               fill="#0b0d16", outline="", tags="overlay")
            dot = cv.create_oval(vx + 24, vy + 25, vx + 32, vy + 33,
                                 fill=colour, outline="", tags="overlay")
            cv.tag_raise(dot, badge)
        cv.tag_raise(tid, badge)

    # -------------------------------------------------- Wiedergabe-Schleife
    def _play_from(self, start, duration, on_end=None):
        """Bildschleife. Faellt nie aus - das Ende wird garantiert erreicht."""
        self._play = {"start": float(start), "dur": float(duration),
                      "t0": time.perf_counter(), "cb": on_end}
        self._frame_tick()

    def _frame_tick(self):
        job = self._play
        if not job or self.phase == "idle":
            return
        now = time.perf_counter()
        elapsed = now - job["t0"]
        if elapsed >= job["dur"]:
            self._play = None
            cb = job["cb"]
            if cb:
                cb()
            return
        fps = max(1.0, float(self.pack.fps))
        try:
            self._show_index(ds.frame_at(self.pack, job["start"] + elapsed))
            if self.screen == "stage":
                if self.phase == "record":
                    self._draw_strip_take(live=True)
                self._strip_head(elapsed)
        except Exception:
            traceback.print_exc()      # darf die Schleife nicht abbrechen
        # Naechsten Termin aus der Startzeit ableiten, nicht aus "jetzt" -
        # sonst summiert sich die Rechenzeit auf und es ruckelt.
        n = int(elapsed * fps) + 1
        delay = int((job["t0"] + n / fps - time.perf_counter()) * 1000)
        self.after(max(1, min(delay, int(1000 / fps))), self._frame_tick)

    def _stop_audio(self):
        self._play = None
        try:
            self.mic.stop_play()
        except Exception:
            pass

    # ------------------------------------------------ Phasen mit Notausgang
    def _set_phase(self, name, expected=0.0):
        """
        Setzt die Phase und merkt sich, wann sie spaetestens vorbei sein muss.
        Laeuft sie ueber, raeumt die Notbremse in _pump() auf - egal was
        schiefgegangen ist, die Bedienung kommt zurueck.
        """
        self.phase = name
        self._phase_deadline = (None if name == "idle"
                                else time.perf_counter() + expected + 5.0)

    def _force_idle(self):
        """Bringt das Spiel aus jedem Zustand zurueck in die Bedienbarkeit."""
        self._phase_deadline = None
        self._play = None
        self._rec_done = True
        if self._rec_guard is not None:
            try:
                self.after_cancel(self._rec_guard)
            except Exception:
                pass
            self._rec_guard = None
        for fn in (self.mic.stop, self.mic.stop_play):
            try:
                fn()
            except Exception:
                pass
        self.phase = "idle"
        try:
            if self.screen == "stage":
                self._overlay(None)
                self.sync()
            elif self.screen == "finale":
                self.b_play.set_text("▶  " + t("play_all"))
        except Exception:
            traceback.print_exc()

    # ------------------------------------------------------------ Aktionen
    def _with_backing(self, audio, start, level=0.6):
        """Legt den Backing Track unter den Ton - laengengenau."""
        back = getattr(self.pack, "backing_audio", None)
        audio = np.asarray(audio, dtype=np.float32)
        if back is None or not len(audio):
            return ds.normalize(audio, 0.95)
        seg = ds.slice_audio(back, start, len(audio) / float(ds.SR))
        seg = ds.fit_len(seg, len(audio))
        return ds.normalize(audio * 0.95 + seg * level, 0.95)

    def play_original(self):
        line = self.current_line()
        if line is None or self.phase != "idle":
            return
        self._set_phase("listen", line.duration)
        self.sync()
        try:
            self._play_backed(line.audio, line.start, 0.6)
        except Exception:
            traceback.print_exc()
            self._force_idle()
            return
        self._play_from(line.start, line.duration, self._end_playback)

    def play_take(self):
        line = self.current_line()
        if line is None or self.phase != "idle" or line.take is None:
            return
        dur = len(line.take) / float(ds.SR)
        self._set_phase("listen", dur)
        self.sync()
        try:
            self._play_backed(line.take, line.start, 0.5)
        except Exception:
            traceback.print_exc()
            self._force_idle()
            return
        self._play_from(line.start, dur, self._end_playback)

    def _end_playback(self):
        self._set_phase("idle")
        self._stop_audio()
        self.sync()

    def do_record(self):
        line = self.current_line()
        if line is None or self.phase != "idle" or not self._net_mine(line):
            return
        self._set_phase("countdown", 3.0)
        self.sync()
        self._count = 3
        self._countdown()

    def _countdown(self):
        if self.phase != "countdown":
            return
        # Erst zeichnen (darf scheitern), dann auf jeden Fall weiterschalten.
        try:
            line = self.current_line()
            if line is not None:
                self.show_frame(line.start)
            if self._count > 0:
                self._overlay(str(self._count), GOLD, 76)
            else:
                self._overlay(t("go"), TEAL, 60)
        except Exception:
            traceback.print_exc()
        if self._count > 0:
            self._count -= 1
            self.after(650, self._countdown)
        else:
            self.after(300, self._begin_record)

    def _begin_record(self):
        if self.phase != "countdown":
            return
        line = self.current_line()
        dur = line.duration + TAIL
        playback = None
        if getattr(self.pack, "backing_audio", None) is not None:
            playback = ds.slice_audio(self.pack.backing_audio, line.start, dur)
        try:
            self.mic.start(playback=playback, device=self._mic_device(),
                           mix=self.net is not None)
        except Exception as ex:
            self._force_idle()
            messagebox.showerror(t("err"), str(ex))
            return
        self._set_phase("record", dur)
        self._rec_done = False
        try:
            self._overlay(t("recording"), RED, 34)
            self.sync()
        except Exception:
            traceback.print_exc()
        self._play_from(line.start, dur, self._finish_record)
        # Sicherheitsnetz: beendet die Aufnahme auch, wenn die Bildschleife
        # aus irgendeinem Grund nicht bis zum Ende kommt.
        self._rec_guard = self.after(int(dur * 1000) + 500,
                                     self._finish_record)

    def _finish_record(self):
        if self._rec_done:
            return
        self._rec_done = True
        if self._rec_guard is not None:
            try:
                self.after_cancel(self._rec_guard)
            except Exception:
                pass
            self._rec_guard = None
        try:
            data = self.mic.stop()
        except Exception:
            traceback.print_exc()
            data = None
        line = self.current_line()
        if line is not None and data is not None and len(data):
            line.take = data
            if self.net:
                self._net_send(line)
        self._play = None
        self._set_phase("idle")
        try:
            self._overlay(None)
            self.sync()
        except Exception:
            traceback.print_exc()

    def clear_take(self):
        line = self.current_line()
        if line is None or self.phase != "idle" or not self._net_mine(line):
            return
        line.take = None
        if self.net:
            self._net_send(line)
        self.sync()

    def goto_line(self, index):
        if self.phase != "idle":
            return
        self.line_i = max(0, min(len(self.pack.lines) - 1, index))
        self._stop_audio()
        self.sync()

    def _own_step(self, step):
        """Naechste/vorige eigene Zeile ab der aktuellen, sonst None."""
        i = self.line_i + step
        while 0 <= i < len(self.pack.lines):
            if self._net_mine(self.pack.lines[i]):
                return i
            i += step
        return None

    def prev_line(self):
        if self.phase != "idle":
            return
        if self.net:
            # Im Mehrspieler nur die eigenen Zeilen - fremde per Leiste
            i = self._own_step(-1)
            if i is not None:
                self.goto_line(i)
        elif self.line_i > 0:
            self.goto_line(self.line_i - 1)

    def next_line(self):
        if self.phase != "idle":
            return
        if self.net:
            i = self._own_step(1)
            if i is None:
                self.net_ready()
            else:
                self.goto_line(i)
            return
        if self.line_i >= len(self.pack.lines) - 1:
            if self.net:
                self.net_ready()
            else:
                self.build_finale()
            return
        self.goto_line(self.line_i + 1)

    def leave_round(self):
        if self.net:
            self.leave_net()
            return
        if messagebox.askyesno(t("title"), t("leave_q")):
            self._stop_audio()
            self._set_phase("idle")
            self.show_menu()

    # ==================================================================
    #  FINALE
    # ==================================================================
    def build_finale(self):
        self._set_phase("idle")
        self._stop_audio()
        try:
            if self.net:
                # Stimmen und Hintergrund getrennt - fuer den Regler
                parts = ds.mix_parts(*ds.render_dub_parts(self.pack))
                mix = ds.normalize(parts[0] + parts[1], 0.97)
            else:
                parts, mix = None, ds.render_dub(self.pack)
        except Exception as ex:
            # z.B. Video ohne Tonspur und kein Backing Track - dann auf der
            # Buehne bleiben, statt mit halb gezeichnetem Finale zu haengen.
            traceback.print_exc()
            messagebox.showerror(t("err"), str(ex))
            return
        self.screen = "finale"
        self.mix = mix
        self.mix_parts = parts
        self._clear_canvas()
        self._backdrop()
        cv = self.cv
        w, h = self.size()
        pad = 34

        if self.net:
            # Im Mehrspieler ist das Finale endgueltig - nur noch verlassen.
            self._btn(pad, 24, 130, 38, "‹  " + t("net_leave"),
                      self.leave_net, "flat", font=("Segoe UI", 11))
        else:
            self._btn(pad, 24, 150, 38, "‹  " + t("back_edit"),
                      self.back_to_stage, "flat", font=("Segoe UI", 11))
        cv.create_text(w / 2, 46, text=t("finale"), fill=TXT,
                       font=("Segoe UI Black", 26))
        self._back_slider(w - pad, 43)
        done = sum(1 for l in self.pack.lines
                   if l.take is not None and len(l.take))
        cv.create_text(w / 2, 76, fill=DIM, font=("Segoe UI", 11),
                       text=t("recorded_n", done, len(self.pack.lines)))

        top = 104
        vw, vh = self._video_size(w, h - top - 226, pad)
        vx = (w - vw) / 2
        self.video_box = (vx, top, vw, vh)
        self._last_idx = None
        round_rect(cv, vx - 8, top - 8, vx + vw + 8, top + vh + 8, r=18,
                   fill="#05060a", outline=EDGE)
        self.video_item = cv.create_image(vx + vw / 2, top + vh / 2,
                                          anchor="center")
        self.overlay_rect = round_rect(cv, vx, top, vx + vw, top + vh, r=12,
                                       fill="#000000", stipple="gray50",
                                       outline="", state="hidden")
        self.overlay_text = cv.create_text(vx + vw / 2, top + vh / 2, text="",
                                           fill=GOLD, state="hidden",
                                           font=("Segoe UI Black", 40))

        # mitlaufender Untertitel
        cy = top + vh + 18
        self.fin_caption = cv.create_text(
            vx + vw / 2, cy, anchor="n", text="", fill=GOLD,
            font=("Segoe UI Semibold", 16), width=vw - 40, justify="center")
        self.fin_caption_h = 48

        py = cy + 56
        round_rect(cv, vx, py, vx + vw, py + 8, r=4, fill=PANEL_HI,
                   outline="")
        self.prog_item = cv.create_rectangle(vx, py, vx, py + 8, fill=ACC,
                                             width=0)
        self.prog_geo = (vx, py, vw)

        by = py + 34
        bw, bh, gapx = 210, 52, 16
        total = bw * 2 + gapx
        bx = (w - total) / 2
        self.b_play = self._btn(bx, by, bw, bh, "▶  " + t("play_all"),
                                self.toggle_finale_play, "go",
                                font=("Segoe UI Semibold", 13))
        self.b_save = self._btn(bx + bw + gapx, by, bw, bh, t("save"),
                                self.export, "ghost",
                                font=("Segoe UI Semibold", 12))
        self.fin_msg = cv.create_text(w / 2, by + bh + 28, text="", fill=DIM,
                                      font=("Segoe UI", 10))
        self.show_frame(0.0)
        self.after(350, self.toggle_finale_play)

    def back_to_stage(self):
        self._stop_audio()
        self._set_phase("idle")
        self.line_i = min(self.line_i, len(self.pack.lines) - 1)
        self.build_stage()

    def toggle_finale_play(self):
        if self.screen != "finale":
            return
        if self.phase == "play":
            self._finale_stop()
            return
        if self.mix is None or not len(self.mix):
            return
        self._set_phase("play", len(self.mix) / float(ds.SR))
        self.b_play.set_text("■  " + t("stop"))
        if self.mix_parts is not None:
            self.mic.play_mix(*self.mix_parts)
        else:
            self.mic.play(self.mix)
        self._play_from(0.0, len(self.mix) / float(ds.SR), self._finale_stop)
        self._finale_progress()

    def _caption_at(self, seconds):
        """Untertitel der Zeile, die gerade laeuft."""
        text = ""
        for l in self.pack.lines:
            if not l.caption:
                continue
            if l.start - 0.2 <= seconds <= l.start + max(l.duration, 0.4) + 0.5:
                text = l.caption
        return text

    def _finale_progress(self):
        if self.phase != "play" or not self._play:
            return
        elapsed = time.perf_counter() - self._play["t0"]
        vx, py, vw = self.prog_geo
        f = min(1.0, elapsed / max(0.01, self._play["dur"]))
        try:
            self.cv.coords(self.prog_item, vx, py, vx + vw * f, py + 8)
            self._fit_text(self.fin_caption, self._caption_at(elapsed),
                           self.fin_caption_h)
        except Exception:
            traceback.print_exc()
        self.after(80, self._finale_progress)

    def _finale_stop(self):
        self._set_phase("idle")
        self._stop_audio()
        if self.screen == "finale":
            self.b_play.set_text("▶  " + t("play_all"))
            vx, py, _vw = self.prog_geo
            self.cv.coords(self.prog_item, vx, py, vx, py + 8)
            self._fit_text(self.fin_caption, "", self.fin_caption_h)

    def export(self):
        os.makedirs(OUT_DIR, exist_ok=True)
        default = "%s_dub.mp4" % pc.safe_name(self.pack.name, "dub")
        path = filedialog.asksaveasfilename(
            initialfile=default, initialdir=OUT_DIR, defaultextension=".mp4",
            filetypes=[("MP4", "*.mp4")])
        if not path:
            return
        self._finale_stop()
        self.b_save.set_enabled(False)
        self.cv.itemconfigure(self.fin_msg, text=t("saving"), fill=GOLD)
        self.update_idletasks()

        mix = self.mix
        if self.mix_parts is not None:
            # Export mit dem eingestellten Hintergrund
            v, b = self.mix_parts
            mix = ds.normalize(v + b * self.mic.back_gain, 0.97)

        def work():
            ds.export_dub_video(self.pack, mix, path)

        def done():
            self.b_save.set_enabled(True)
            self.cv.itemconfigure(self.fin_msg, text="", fill=DIM)
            messagebox.showinfo(t("title"), t("saved", path))

        def failed(msg):
            # Im Finale bleiben: zurueck ins Menue hiesse, alle Aufnahmen
            # dieser Runde zu verlieren - nur weil z.B. die Datei gesperrt war.
            if self.screen == "finale":
                self.b_save.set_enabled(True)
                self.cv.itemconfigure(self.fin_msg, text="", fill=DIM)
            messagebox.showerror(t("err"), msg)
        self._run_bg(work, done, on_error=failed)

    # ==================================================================
    #  MEHRSPIELER / MULTIPLAYER
    # ==================================================================
    def _ask(self, title, fields, check=None):
        """
        Kleiner modaler Dialog. fields: [(key, label, default)],
        check: (key, label, value, enabled, note). Gibt dict oder None.
        """
        win = tk.Toplevel(self)
        win.title(title)
        win.configure(bg=PANEL)
        win.transient(self)
        win.resizable(False, False)
        frm = tk.Frame(win, bg=PANEL, padx=24, pady=20)
        frm.pack(fill="both", expand=True)
        values = {}
        entries = []
        for r, (key, label, default) in enumerate(fields):
            tk.Label(frm, text=label, bg=PANEL, fg=DIM,
                     font=("Segoe UI", 10)).grid(row=r, column=0, sticky="w",
                                                 pady=5, padx=(0, 14))
            var = tk.StringVar(value=default)
            ent = tk.Entry(frm, textvariable=var, width=38, bg=PANEL_HI,
                           fg=TXT, insertbackground=TXT, relief="flat",
                           font=("Segoe UI", 11), highlightthickness=1,
                           highlightbackground=EDGE, highlightcolor=ACC)
            ent.grid(row=r, column=1, sticky="we", pady=5, ipady=4)
            values[key] = var
            entries.append((ent, default))
        # Fokus ins erste leere Feld, sonst ins erste
        targets = [e for e, d in entries if not d] or [e for e, _d in entries]
        if targets:
            targets[0].focus_set()
        row = len(fields)
        if check:
            key, label, value, enabled, note = check
            var = tk.BooleanVar(value=value)
            tk.Checkbutton(frm, text=label, variable=var, bg=PANEL, fg=TXT,
                           selectcolor=PANEL_HI, activebackground=PANEL,
                           activeforeground=TXT, disabledforeground=DIM,
                           font=("Segoe UI", 10),
                           state="normal" if enabled else "disabled"
                           ).grid(row=row, column=0, columnspan=2,
                                  sticky="w", pady=(10, 0))
            row += 1
            if note:
                tk.Label(frm, text=note, bg=PANEL, fg=DIM, justify="left",
                         font=("Segoe UI", 9), wraplength=440
                         ).grid(row=row, column=0, columnspan=2, sticky="w")
                row += 1
            values[key] = var
        result = {}

        def ok(_e=None):
            result.update((k, v.get()) for k, v in values.items())
            win.destroy()

        bar = tk.Frame(frm, bg=PANEL)
        bar.grid(row=row, column=0, columnspan=2, sticky="e", pady=(18, 0))
        style = dict(relief="flat", font=("Segoe UI Semibold", 10), padx=16,
                     pady=6, cursor="hand2", bd=0)
        tk.Button(bar, text=t("cancel"), command=win.destroy, bg=PANEL_HI,
                  fg=TXT, activebackground=EDGE, activeforeground=TXT,
                  **style).pack(side="right", padx=(8, 0))
        tk.Button(bar, text="OK", command=ok, bg=ACC, fg="#ffffff",
                  activebackground=ACC_HI, activeforeground="#ffffff",
                  **style).pack(side="right")
        win.bind("<Return>", ok)
        win.bind("<Escape>", lambda _e: win.destroy())
        win.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - win.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - win.winfo_height()) // 3
        win.geometry("+%d+%d" % (max(0, x), max(0, y)))
        try:
            win.grab_set()
        except tk.TclError:
            pass
        self.wait_window(win)
        return result or None

    def _menu_busy(self, text):
        self.cv.itemconfigure(self.status_item, text=text, fill=GOLD)
        for b in self.buttons:
            b.set_enabled(False)
        self._loading = True
        self.update_idletasks()

    # ---------------------------------------------------------- Hosten
    def host_game(self):
        if not self.packs or not self.mic.available or not HAVE_PIL:
            return
        have_cf = bool(net.find_cloudflared())
        res = self._ask(t("host_t"), [
            ("name", t("your_name"), self.cfg.get("net_name") or ""),
            ("port", t("port"),
             str(self.cfg.get("net_port") or net.DEFAULT_PORT)),
        ], check=("tunnel", t("use_tunnel"),
                  have_cf and self.cfg.get("net_tunnel", True), have_cf,
                  t("tunnel_ok") if have_cf else t("tunnel_missing")))
        if not res:
            return
        try:
            port = int(res["port"])
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            messagebox.showerror(t("err"), t("bad_port"))
            return
        name = res["name"].strip() or "Host"
        self.cfg.update(net_name=name, net_port=port)
        if have_cf:
            self.cfg["net_tunnel"] = bool(res["tunnel"])
        save_cfg(self.cfg)
        pack = self.packs[self.sel_pack]
        want_tunnel = have_cf and res["tunnel"]
        self._menu_busy(t("loading"))
        got = {}

        def work():
            self._prepare_pack(pack)
            room = net.Room(pack)
            server = net.Server(room, port)
            try:
                room.pack_zip()          # vorab, damit Gaeste nicht warten
                room.prepare_web_video()  # MP4 fuer Browser, im Hintergrund
            except Exception:
                server.close()
                raise
            got.update(room=room, server=server)
            if want_tunnel:
                try:
                    got["tunnel"], got["url"] = net.start_quick_tunnel(
                        server.port)
                except Exception as ex:
                    got["tunnel_err"] = str(ex)

        def done():
            self._loading = False
            room, server = got["room"], got["server"]
            client = net.Client("127.0.0.1:%d" % server.port, room.code)
            client.player, client.token = room.join(name, host=True)
            s = NetSession(client, server, room)
            s.tunnel, s.tunnel_url = got.get("tunnel"), got.get("url")
            s.state = room.snapshot()
            client.version = s.state["version"]
            self._use_pack(pack)
            self._net_begin(s)
            self.build_lobby()
            if got.get("tunnel_err"):
                messagebox.showwarning(t("title"),
                                       t("tunnel_fail", got["tunnel_err"]))

        def failed(msg):
            self._loading = False
            self.show_menu()
            messagebox.showerror(t("err"), msg)
        self._run_bg(work, done, on_error=failed)

    # -------------------------------------------------------- Beitreten
    def join_game(self):
        if not self.mic.available or not HAVE_PIL:
            return
        res = self._ask(t("join_t"), [
            ("addr", t("address"), self.cfg.get("net_addr") or ""),
            ("code", t("room_code"), ""),
            ("name", t("your_name"), self.cfg.get("net_name") or ""),
        ])
        if not res:
            return
        addr, code = res["addr"].strip(), res["code"].strip()
        if not addr or not code:
            messagebox.showerror(t("err"), t("need_addr"))
            return
        name = res["name"].strip() or "Player"
        self.cfg.update(net_addr=addr, net_name=name)
        save_cfg(self.cfg)
        self._menu_busy(t("net_connecting"))
        got = {}

        def work():
            client = net.Client(addr, code)
            got["state"] = client.join(name)
            got["client"] = client

        def done():
            self._loading = False
            s = NetSession(got["client"])
            s.state = got["state"]
            s.client.version = s.state["version"]
            self.pack = None
            self._net_begin(s)
            self.build_lobby()
            self._net_fetch_pack()

        def failed(msg):
            self._loading = False
            self.show_menu()
            messagebox.showerror(t("net_join_fail"), msg)
        self._run_bg(work, done, on_error=failed)

    def _net_fetch_pack(self):
        """Gast: Pack holen (falls noetig), laden, dann 'bereit' melden."""
        s = self.net
        got = {}

        def progress(f):
            try:
                s.client.set_status(progress=f)
            except Exception:
                pass

        def work():
            folder = s.client.download_pack(s.state, progress)
            pack = ds.load_pack(folder)
            if pack is None:
                raise net.NetError(t("net_bad_pack"))
            pack.name = s.state["pack"]["name"]   # ohne Hash-Anhang
            self._prepare_pack(pack)
            got["pack"] = pack

        def done():
            if self.net is not s:
                return
            self._use_pack(got["pack"])
            self._net_bg(lambda: s.client.set_status(ready=True,
                                                     progress=1.0))
            self._net_apply_takes()
            self._net_follow_phase()
            if self.screen == "lobby":
                self.build_lobby()

        def failed(msg):
            if self.net is not s:
                return
            self.show_menu()
            messagebox.showerror(t("err"), msg)
        self._run_bg(work, done, on_error=failed)

    # ------------------------------------------------- Sitzung steuern
    def _net_bg(self, fn):
        """Netzaufruf ohne Rueckmeldung im Hintergrund."""
        def run():
            try:
                fn()
            except Exception:
                traceback.print_exc()
        threading.Thread(target=run, daemon=True).start()

    def _net_begin(self, s):
        self.net = s
        self.mic.back_gain = float(self.cfg.get("backing_vol", 1.0))
        self.lobby_scroll = 0
        s.client.start_polling(
            lambda kind, payload: self.msgq.put((kind, (s, payload))))

    def _net_close(self, wait=False):
        s, self.net = self.net, None
        self.mic.back_gain = 1.0      # Einzelspieler: wie immer
        if s is None:
            return
        if wait:
            s.close()
        else:
            self._net_bg(s.close)

    def leave_net(self):
        s = self.net
        if s is None:
            return
        q = t("net_leave_host_q") if s.is_host else t("net_leave_q")
        if not messagebox.askyesno(t("title"), q):
            return
        self._force_idle()
        self._stop_audio()
        self.show_menu()

    def _net_lost(self, msg):
        if self.net is None:
            return
        self._force_idle()
        self._stop_audio()
        self.show_menu()
        messagebox.showerror(t("net_lost_t"), msg)

    def _on_net_msg(self, kind, s, payload):
        if s is not self.net:
            return                    # Nachricht einer alten Runde
        if kind == "net_lost":
            self._net_lost(payload)
            return
        if kind == "net_wait":
            s.trouble = payload
        elif kind == "net_back":
            s.trouble = None
            self._net_retry()
        elif kind == "net":
            s.state = payload
            if payload.get("phase") == "closed":
                self._net_lost(t("net_closed"))
                return
            self._net_apply_takes()
            self._net_retry()
            self._net_follow_phase()
        self._net_refresh()

    def _net_refresh(self):
        if self.screen == "lobby" and not self._loading:
            self.build_lobby()
        elif self.screen == "stage":
            self.sync()
        elif self.screen == "waiting" and self.phase == "idle":
            self.build_waiting()      # nicht mitten im Abspielen neu zeichnen
        elif self.screen == "assembling":
            self.build_assembling()

    def _net_follow_phase(self):
        """Geht mit, wenn der Host startet oder zurueck in die Lobby holt."""
        s = self.net
        if s is None or self.pack is None or not s.state:
            return
        phase = s.state.get("phase")
        if phase == "recording" and self.screen == "lobby":
            # Mit der ersten eigenen, noch leeren Zeile anfangen
            self.line_i = 0
            for i, l in enumerate(self.pack.lines):
                if self._net_mine(l) and l.take is None:
                    self.line_i = i
                    break
            self.build_stage()
        elif phase == "lobby" and self.screen in ("stage", "finale",
                                                   "waiting", "assembling"):
            if self.phase not in ("idle", "listen", "play"):
                # Nicht mitten in die Aufnahme grätschen - gleich nochmal.
                self.after(500, self._net_follow_phase)
                return
            s.want_done = False
            self._force_idle()
            self._stop_audio()
            self.build_lobby()
        elif phase == "finale" and self.screen != "finale":
            if self.phase in ("countdown", "record"):
                self.after(500, self._net_follow_phase)
                return
            self._force_idle()
            self._stop_audio()
            if self._net_takes_complete():
                self.build_finale()
            elif self.screen != "assembling":
                self.build_assembling()

    def _net_takes_complete(self):
        """Liegen alle Aufnahmen vom Host auch hier?"""
        s = self.net
        takes = s.state.get("takes", {})
        return not s.fetching and all(
            s.revs.get(f) == info["rev"] or f in s.unsent
            for f, info in takes.items())

    # ------------------------------------------------------- Abfragen
    def _net_owner(self, line):
        s = self.net
        if s is None or not s.state or line is None:
            return None
        return s.state["owner"].get(line.file)

    def _net_mine(self, line):
        """Im Einzelspieler gehoert jede Zeile dem Spieler."""
        if self.net is None:
            return True
        return line is not None and self._net_owner(line) == self.net.me

    def _net_player(self, pid):
        s = self.net
        for p in ((s.state or {}).get("players", []) if s else []):
            if p["id"] == pid:
                return p
        return None

    def _net_hint(self):
        s = self.net
        lines = self.pack.lines
        if s.trouble:
            return t("net_trouble")
        done = sum(1 for l in lines if l.take is not None and len(l.take))
        parts = [t("recorded_n", done, len(lines))]
        mine_left = sum(1 for l in lines
                        if self._net_mine(l) and l.take is None)
        if mine_left:
            parts.append(t("net_yours_left", mine_left))
        else:
            waiting = {}
            for l in lines:
                pid = self._net_owner(l)
                if l.take is None and pid is not None:
                    waiting[pid] = waiting.get(pid, 0) + 1
            if waiting:
                parts.append(t("net_waiting", ", ".join(
                    "%s (%d)" % ((self._net_player(pid) or {}).get("name",
                                                                   "?"), n)
                    for pid, n in waiting.items())))
        if s.unsent:
            parts.append(t("net_unsent", len(s.unsent)))
        return "   ·   ".join(parts)

    # ------------------------------------------------ Aufnahmen tauschen
    def _net_send(self, line):
        """Schickt die eigene Aufnahme (oder ihr Loeschen) an den Host."""
        s = self.net
        f, data = line.file, line.take
        op = "put" if data is not None else "del"
        s.unsent[f] = op
        s.failed.discard(f)

        def work():
            if op == "put":
                s.client.upload_take(f, data)
            else:
                s.client.delete_take(f)

        def done():
            # Nur abhaken, wenn nicht inzwischen neu aufgenommen wurde.
            if s.unsent.get(f) == op and line.take is data:
                s.unsent.pop(f, None)
            if self.net is s:
                self._net_push_done()
                self._net_refresh()

        def failed(msg):
            if ("not your line" in msg or "unknown line" in msg
                    or "game finished" in msg):
                s.unsent.pop(f, None)     # neu verteilt oder schon Finale
            elif s.unsent.get(f) == op and line.take is data:
                s.failed.add(f)
            if self.net is s:
                self._net_refresh()
        self._run_bg(work, done, on_error=failed)

    def _net_retry(self):
        s = self.net
        if s is None or self.pack is None or s.trouble:
            return
        lines = dict((l.file, l) for l in self.pack.lines)
        for f in list(s.failed):
            s.failed.discard(f)
            if f in lines and self._net_mine(lines[f]):
                self._net_send(lines[f])
            else:
                s.unsent.pop(f, None)

    def _net_apply_takes(self):
        """Gleicht die Aufnahmen mit dem Stand des Hosts ab."""
        s = self.net
        if s is None or self.pack is None or not s.state:
            return
        lines = dict((l.file, l) for l in self.pack.lines)
        takes = s.state.get("takes", {})
        for f, info in takes.items():
            line = lines.get(f)
            if line is None or s.revs.get(f) == info["rev"] or f in s.unsent:
                continue
            if info["player"] == s.me and line.take is not None:
                s.revs[f] = info["rev"]   # die eigene, liegt schon hier
                continue
            self._net_fetch(f, info["rev"])
        for f in list(s.revs):
            if f not in takes:
                s.revs.pop(f)
                if f in lines and f not in s.unsent:
                    lines[f].take = None

    def _net_fetch(self, f, rev):
        s = self.net
        if f in s.fetching:
            return
        s.fetching.add(f)
        got = {}

        def work():
            got["data"] = s.client.fetch_take(f)

        def done():
            s.fetching.discard(f)
            if self.net is not s or self.pack is None:
                return
            line = next((l for l in self.pack.lines if l.file == f), None)
            if line is not None and f not in s.unsent:
                line.take = got["data"]
                s.revs[f] = rev
            cur = s.state.get("takes", {}).get(f)
            if cur and cur["rev"] != rev:
                self._net_fetch(f, cur["rev"])
            if self.screen == "finale":
                self.cv.itemconfigure(self.fin_msg, text=t("net_new_takes"),
                                      fill=GOLD)
            self._net_follow_phase()
            self._net_refresh()

        def failed(_msg):
            s.fetching.discard(f)
        self._run_bg(work, done, on_error=failed)

    # ------------------------------------------------------- Bereit
    def net_ready(self):
        """Letzte Zeile: bereit melden und auf die anderen warten."""
        s = self.net
        self._stop_audio()
        self._set_phase("idle")
        s.want_done = True
        self.build_waiting()
        self._net_push_done()

    def _net_push_done(self):
        # Erst wenn alle eigenen Aufnahmen beim Host sind - sonst beginnt
        # das Finale womoeglich ohne die letzte.
        s = self.net
        if s is None or not s.want_done or s.unsent:
            return
        self._net_bg(lambda: s.client.set_done(True))

    def net_back_to_lines(self):
        s = self.net
        s.want_done = False
        self._stop_audio()
        self._set_phase("idle")
        self._net_bg(lambda: s.client.set_done(False))
        self.back_to_stage()

    def build_waiting(self):
        s = self.net
        if s is None:
            self.show_menu()
            return
        self.screen = "waiting"
        self._clear_canvas()
        self._backdrop()
        cv = self.cv
        w, h = self.size()
        pad = 34
        st = s.state or {}

        self._btn(pad, 24, 130, 38, "‹  " + t("net_leave"), self.leave_net,
                  "flat", font=("Segoe UI", 11))
        cv.create_text(w / 2, 44, text=t("wait_title"), fill=TXT,
                       font=("Segoe UI Black", 24))
        self._back_slider(w - pad, 43)
        cv.create_text(w / 2, 76, text=t("wait_sub"), fill=DIM,
                       font=("Segoe UI", 11))

        # Video links - fuer "Meine Zeilen abspielen"
        top = 112
        vw, vh = self._video_size(int(w * 0.6), h - top - 160, pad)
        vx = pad + 16
        self.video_box = (vx, top, vw, vh)
        self._last_idx = None
        round_rect(cv, vx - 8, top - 8, vx + vw + 8, top + vh + 8, r=18,
                   fill="#05060a", outline=EDGE)
        self.video_item = cv.create_image(vx + vw / 2, top + vh / 2,
                                          anchor="center")
        self.overlay_rect = round_rect(cv, vx, top, vx + vw, top + vh, r=12,
                                       fill="#000000", stipple="gray50",
                                       outline="", state="hidden")
        self.overlay_text = cv.create_text(vx + vw / 2, top + vh / 2, text="",
                                           fill=GOLD, state="hidden",
                                           font=("Segoe UI Black", 40))
        self.wait_caption = cv.create_text(
            vx + vw / 2, top + vh + 18, anchor="n", text="", fill=GOLD,
            font=("Segoe UI Semibold", 13), width=vw - 20, justify="center")

        # Fortschritt aller Spieler rechts
        px0, px1 = vx + vw + 28, w - pad
        round_rect(cv, px0, top - 8, px1, top + vh + 8, r=16, fill=PANEL,
                   outline=EDGE)
        cv.create_text(px0 + 18, top + 14, anchor="w", text=t("players"),
                       fill=DIM, font=("Segoe UI Semibold", 10))
        owner, takes = st.get("owner", {}), st.get("takes", {})
        players = [p for p in st.get("players", []) if not p.get("left")]
        for i, p in enumerate(players):
            y = top + 44 + i * 50
            if y > top + vh - 20:
                break
            total = sum(1 for o in owner.values() if o == p["id"])
            got = sum(1 for f, o in owner.items()
                      if o == p["id"] and f in takes)
            cv.create_oval(px0 + 18, y - 6, px0 + 30, y + 6, fill=p["color"],
                           outline="")
            name = p["name"] + ("  (%s)" % t("you") if p["id"] == s.me
                                else "")
            cv.create_text(px0 + 40, y, anchor="w", text=name, fill=TXT,
                           font=("Segoe UI Semibold", 11))
            if not p.get("online"):
                status, col = t("st_off"), RED
            elif p.get("done"):
                status, col = t("st_done"), TEAL
            else:
                status, col = t("st_working"), GOLD
            cv.create_text(px0 + 40, y + 20, anchor="w",
                           text="%s   ·   %s" % (t("lines_done", got, total),
                                                status),
                           fill=col, font=("Segoe UI", 10))

        # Knoepfe
        mine = [l for l in self.pack.lines
                if self._net_mine(l) and l.take is not None]
        by = min(top + vh + 64, h - 76)
        self.wait_caption_h = max(16, by - (top + vh + 18) - 6)
        self.b_replay = self._btn(vx, by, 230, 48, "▶  " + t("replay_mine"),
                                  self.replay_mine, "go",
                                  font=("Segoe UI Semibold", 12))
        self.b_replay.set_enabled(bool(mine))
        self._btn(vx + 246, by, 240, 48, "‹  " + t("back_mine"),
                  self.net_back_to_lines, "ghost")
        if s.is_host:
            self._btn(w - pad - 200, by, 200, 48, t("finish_now"),
                      s.room.finish, "primary")
        if s.trouble:
            msg = t("net_trouble")
        elif s.unsent:
            msg = t("net_unsent", len(s.unsent))
        elif not mine:
            msg = t("no_takes_mine")
        else:
            msg = ""
        cv.create_text(w / 2, by + 70, text=msg, fill=DIM,
                       font=("Segoe UI", 10))
        self.show_frame(mine[0].start if mine else 0.0)

    def replay_mine(self):
        """Spielt die eigenen Aufnahmen nacheinander zum Video ab."""
        if self.phase != "idle":
            self._stop_audio()
            self._set_phase("idle")
            self.build_waiting()
            return
        queue_ = [l for l in self.pack.lines
                  if self._net_mine(l) and l.take is not None]
        if queue_:
            self.b_replay.set_text("■  " + t("stop"))
            self._replay_next(queue_, 0)

    def _replay_next(self, queue_, i):
        if self.screen != "waiting" or (i > 0 and self.phase != "listen"):
            return
        if i >= len(queue_):
            self._stop_audio()
            self._set_phase("idle")
            self.build_waiting()
            return
        line = queue_[i]
        dur = len(line.take) / float(ds.SR)
        self._set_phase("listen", dur)
        self._fit_text(self.wait_caption, line.caption or line.name,
                       self.wait_caption_h, size=13, min_size=9)
        try:
            self._play_backed(line.take, line.start, 0.5)
        except Exception:
            traceback.print_exc()
        self._play_from(line.start, dur,
                        lambda: self._replay_next(queue_, i + 1))

    def build_assembling(self):
        """Alle sind bereit - die letzten Aufnahmen werden noch geholt."""
        s = self.net
        if s is None:
            self.show_menu()
            return
        self.screen = "assembling"
        self._clear_canvas()
        self._backdrop()
        cv = self.cv
        w, h = self.size()
        takes = (s.state or {}).get("takes", {})
        here = sum(1 for f, info in takes.items()
                   if s.revs.get(f) == info["rev"] or f in s.unsent)
        cv.create_text(w / 2, h / 2 - 20, text=t("assembling"), fill=TXT,
                       font=("Segoe UI Black", 24))
        cv.create_text(w / 2, h / 2 + 22, fill=DIM, font=("Segoe UI", 11),
                       text=t("assembling_n", here, len(takes)))

    # ------------------------------------------------------------ Lobby
    def _copy(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        try:
            self.cv.itemconfigure(self.lobby_msg, text=t("copied"), fill=TEAL)
        except Exception:
            pass

    def _net_addresses(self):
        """(Bezeichnung, Anzeige, zum Kopieren oder None)"""
        s = self.net
        if not s.is_host:
            return [(t("joined_addr"), s.client.base, s.client.base)]
        port = s.server.port
        out = []
        if s.tunnel_url:
            # Browser erlauben das Mikrofon nur ueber https - also nur hier.
            link = "%s/#code=%s" % (s.tunnel_url, s.client.code)
            out.append((t("addr_browser"), link.split("://", 1)[1], link))
            out.append((t("addr_tunnel"), s.tunnel_url.split("://", 1)[1],
                        s.tunnel_url))
        lan = "%s:%d" % (net.lan_ip(), port)
        out.append((t("addr_lan"), lan, lan))
        out.append((t("addr_inet"), t("addr_inet_v", port), None))
        return out

    def _lobby_units(self):
        """Zeilen fuer die Rollenliste: nach Figur oder einzeln."""
        if self.lobby_by_line:
            return [("%d  %s" % (l.index + 1, l.name), [l])
                    for l in self.pack.lines]
        return net.line_groups(self.pack.lines)

    def _lobby_cycle(self, files):
        """
        Host: Rolle reihum weitergeben (frei -> Spieler 1 -> ... -> frei).
        Alle anderen: freie Rolle nehmen, eigene abgeben.
        """
        s = self.net
        if s is None:
            return
        if s.is_host:
            order = [None] + s.room.active_ids()
            cur = s.room.owner.get(files[0])
            nxt = order[(order.index(cur) + 1) % len(order)] \
                if cur in order else None
            s.room.assign_all(dict((f, nxt) for f in files))
            return
        owner = (s.state or {}).get("owner", {})
        owners = set(owner.get(f) for f in files)
        if owners == {s.me}:
            take = False
        elif owners <= {None, s.me}:
            take = True
        else:
            self.cv.itemconfigure(self.lobby_msg, text=t("role_taken"),
                                  fill=RED)
            return

        def failed(msg):
            if self.screen == "lobby":
                self.cv.itemconfigure(self.lobby_msg, fill=RED,
                                      text=t("role_taken")
                                      if "taken" in msg else msg)
        self._run_bg(lambda: s.client.claim(files, take), lambda: None,
                     on_error=failed)

    def net_auto_split(self):
        s = self.net
        if s and s.is_host and self.pack:
            s.room.auto_split()

    def _toggle_lobby_view(self):
        self.lobby_by_line = not self.lobby_by_line
        self.lobby_scroll = 0
        self.build_lobby()

    def build_lobby(self):
        s = self.net
        if s is None:
            self.show_menu()
            return
        self.screen = "lobby"
        self._clear_canvas()
        self._backdrop()
        self.lobby_rows = []
        cv = self.cv
        w, h = self.size()
        st = s.state or {}
        players = [p for p in st.get("players", []) if not p.get("left")]

        self._btn(34, 24, 130, 38, "‹  " + t("net_leave"), self.leave_net,
                  "flat", font=("Segoe UI", 11))
        cv.create_text(w / 2, 40, text=t("lobby"), fill=TXT,
                       font=("Segoe UI Black", 22))
        cv.create_text(w / 2, 72, text=st.get("pack", {}).get("name", ""),
                       fill=DIM, font=("Segoe UI", 11))

        top, bottom = 104, h - 100
        lx0, lx1 = 50, int(w * 0.42)
        rx0, rx1 = lx1 + 22, w - 50

        # ---- Raumcode
        round_rect(cv, lx0, top, lx1, top + 92, r=16, fill=PANEL, outline=EDGE)
        cv.create_text(lx0 + 20, top + 22, anchor="w", text=t("room_code"),
                       fill=DIM, font=("Segoe UI Semibold", 10))
        cv.create_text(lx0 + 20, top + 60, anchor="w", text=s.client.code,
                       fill=GOLD, font=("Consolas", 28, "bold"))
        self._btn(lx1 - 104, top + 42, 86, 34, t("copy"),
                  lambda: self._copy(s.client.code), "ghost",
                  font=("Segoe UI", 10))

        # ---- Adressen
        addrs = self._net_addresses()
        ay = top + 106
        ah = 38 + 48 * len(addrs)
        round_rect(cv, lx0, ay, lx1, ay + ah, r=16, fill=PANEL, outline=EDGE)
        cv.create_text(lx0 + 20, ay + 22, anchor="w",
                       text=t("share_addr") if s.is_host
                       else t("joined_addr"),
                       fill=DIM, font=("Segoe UI Semibold", 10))
        for i, (label, text, value) in enumerate(addrs):
            y = ay + 40 + i * 48
            cv.create_text(lx0 + 20, y + 8, anchor="w", text=label,
                           fill=DIM, font=("Segoe UI", 9))
            cv.create_text(lx0 + 20, y + 28, anchor="w", text=text,
                           fill=TXT if value else DIM,
                           font=("Consolas", 10), width=lx1 - lx0 - 130)
            if value:
                self._btn(lx1 - 104, y + 4, 86, 30, t("copy"),
                          lambda v=value: self._copy(v), "ghost",
                          font=("Segoe UI", 10))

        # ---- Spieler
        py = ay + ah + 14
        round_rect(cv, lx0, py, lx1, bottom, r=16, fill=PANEL, outline=EDGE)
        cv.create_text(lx0 + 20, py + 22, anchor="w", text=t("players"),
                       fill=DIM, font=("Segoe UI Semibold", 10))
        for i, p in enumerate(players):
            y = py + 50 + i * 30
            if y > bottom - 14:
                break
            cv.create_oval(lx0 + 20, y - 6, lx0 + 32, y + 6, fill=p["color"],
                           outline="")
            tags = []
            if p.get("host"):
                tags.append(t("host_tag"))
            if p["id"] == s.me:
                tags.append(t("you"))
            name = p["name"] + ("  (%s)" % ", ".join(tags) if tags else "")
            cv.create_text(lx0 + 42, y, anchor="w", text=name, fill=TXT,
                           font=("Segoe UI Semibold", 11))
            if not p.get("online"):
                status, col = t("st_off"), RED
            elif p.get("ready"):
                status, col = t("st_ready"), TEAL
            elif p.get("progress", 0) >= 0.99:
                status, col = t("st_prep"), GOLD
            else:
                status, col = t("st_dl", int(p.get("progress", 0) * 100)), GOLD
            cv.create_text(lx1 - 20, y, anchor="e", text=status, fill=col,
                           font=("Segoe UI", 10))

        # ---- Rollen
        round_rect(cv, rx0, top, rx1, bottom, r=16, fill=PANEL, outline=EDGE)
        cv.create_text(rx0 + 20, top + 24, anchor="w", text=t("roles"),
                       fill=TXT, font=("Segoe UI Semibold", 13))
        cv.create_text(rx0 + 20, top + 46, anchor="w",
                       text=t("roles_hint") if s.is_host
                       else t("roles_pick"), fill=DIM,
                       font=("Segoe UI", 9))
        if self.pack is None:
            cv.create_text((rx0 + rx1) / 2, (top + bottom) / 2,
                           text=t("dl_pack"), fill=GOLD,
                           font=("Segoe UI Semibold", 12))
        else:
            self._btn(rx1 - 150, top + 14, 132, 30,
                      t("by_char") if self.lobby_by_line else t("by_line"),
                      self._toggle_lobby_view, "ghost",
                      font=("Segoe UI", 10))
            owner = st.get("owner", {})
            units = self._lobby_units()
            row_h, y0 = 42, top + 64
            per_page = max(1, int((bottom - 12 - y0) // row_h))
            self.lobby_scroll = max(0, min(self.lobby_scroll,
                                           len(units) - per_page))
            for i, (label, lines) in enumerate(
                    units[self.lobby_scroll:self.lobby_scroll + per_page]):
                y = y0 + i * row_h
                pids = []
                for l in lines:
                    pid = owner.get(l.file)
                    if pid not in pids:
                        pids.append(pid)
                ps = [self._net_player(pid) or {"name": t("role_free")}
                      for pid in pids]
                round_rect(cv, rx0 + 14, y, rx1 - 14, y + row_h - 6, r=10,
                           fill=PANEL_HI, outline="")
                seg = (row_h - 6) / float(max(1, len(ps)))
                for k, p in enumerate(ps):
                    cv.create_rectangle(rx0 + 14, y + k * seg, rx0 + 20,
                                        y + (k + 1) * seg, width=0,
                                        fill=p.get("color", DIM))
                cv.create_text(rx0 + 32, y + (row_h - 6) / 2, anchor="w",
                               text=label, fill=TXT,
                               font=("Segoe UI Semibold", 11),
                               width=(rx1 - rx0) * 0.45)
                secs = sum(l.duration for l in lines)
                meta = "%s · %.1f s" % (t("lines_n", len(lines)), secs)
                cv.create_text(rx0 + (rx1 - rx0) * 0.55, y + (row_h - 6) / 2,
                               anchor="w", text=meta, fill=DIM,
                               font=("Segoe UI", 9))
                cv.create_text(rx1 - 28, y + (row_h - 6) / 2, anchor="e",
                               text=" / ".join(p.get("name", "?")
                                               for p in ps),
                               fill=ps[0].get("color", DIM) if ps else DIM,
                               font=("Segoe UI Semibold", 10))
                self.lobby_rows.append(
                    ((rx0 + 14, y, rx1 - 14, y + row_h - 6),
                     [l.file for l in lines]))
            if len(units) > per_page:
                cv.create_text((rx0 + rx1) / 2, bottom - 10,
                               text="%d / %d" % (min(len(units),
                                                     self.lobby_scroll
                                                     + per_page),
                                                 len(units)),
                               fill=DIM, font=("Segoe UI", 9))

        # ---- untere Leiste
        by = h - 76
        all_ready = bool(players) and all(p.get("ready") and p.get("online")
                                          for p in players)
        if s.is_host:
            self._btn(50, by, 200, 46, t("auto_split"), self.net_auto_split,
                      "ghost")
            go = self._btn(w - 250, by, 200, 46, t("net_start"),
                           s.room.start, "go",
                           font=("Segoe UI Semibold", 13))
            go.set_enabled(all_ready and self.pack is not None)
            msg = t("can_start") if all_ready else t("wait_ready")
            free = sum(1 for pid in st.get("owner", {}).values()
                       if pid is None)
            if all_ready and free:
                msg = t("unassigned_n", free)
        else:
            msg = t("wait_host") if self.pack is not None else t("dl_pack")
        if s.trouble:
            msg = t("net_trouble")
        self.lobby_msg = cv.create_text(w / 2, by + 23, text=msg, fill=DIM,
                                        font=("Segoe UI", 10))

    # ------------------------------------------------------- Hintergrund
    def _run_bg(self, fn, on_done, on_error=None):
        def wrapper():
            try:
                fn()
                self.msgq.put(("done", on_done))
            except Exception as ex:
                traceback.print_exc()
                if on_error is not None:
                    # ex verschwindet am Ende des except-Blocks - Text binden.
                    msg = str(ex)
                    self.msgq.put(("done", lambda: on_error(msg)))
                else:
                    self.msgq.put(("error", str(ex)))
        threading.Thread(target=wrapper, daemon=True).start()

    def _pump(self):
        try:
            while True:
                kind, payload = self.msgq.get_nowait()
                if kind == "done":
                    payload()
                elif kind == "error":
                    self._loading = False
                    messagebox.showerror(t("err"), payload)
                    self.show_menu()
                elif kind == "thumb":
                    # Mehrere Bilder kurz nacheinander: nur einmal neu zeichnen.
                    if not self._thumb_redraw:
                        self._thumb_redraw = True
                        self.after(150, self._redraw_thumbs)
                elif kind == "update":
                    upd.note_checked(self.cfg)
                    self.cfg["upd_cache"] = payload
                    save_cfg(self.cfg)
                    if payload.get("newer") and not self.upd_dismissed:
                        self.upd_info = payload
                        if self.screen == "menu":
                            self.show_menu()
                elif kind in ("net", "net_wait", "net_back", "net_lost"):
                    self._on_net_msg(kind, *payload)
                elif kind == "upd_say":
                    self._upd_say(payload)
                elif kind == "upd_quit":
                    self._upd_say(t("upd_swap"))
                    self.after(700, self._on_close)
                elif kind == "upd_error":
                    self.upd_busy = False
                    self.show_menu()
                    messagebox.showerror(t("upd_fail_t"), t("upd_fail", payload))
        except queue.Empty:
            pass
        # Notbremse: haengt eine Phase laenger als erwartet, aufraeumen.
        if (self._phase_deadline is not None
                and time.perf_counter() > self._phase_deadline):
            print("DubStage: Phase '%s' haengt - wird zurueckgesetzt."
                  % self.phase)
            self._force_idle()
        self.after(60, self._pump)

    def _redraw_thumbs(self):
        self._thumb_redraw = False
        if self.screen == "menu" and not self._busy and not self._loading:
            self.show_menu()

    def _on_close(self):
        # Siehe DubForge: beim Update haengt ein Skript am Prozessende.
        for step in (self._stop_audio, lambda: save_cfg(self.cfg),
                     lambda: self._net_close(wait=True)):
            try:
                step()
            except Exception:
                pass
        self.destroy()


if __name__ == "__main__":
    appwin.set_app_id("DubStage")
    Game().mainloop()

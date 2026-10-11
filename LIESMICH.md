# DubForge & DubStage

Szenen aus Videos selbst nachsprechen. **DubForge** zerlegt ein Video in einsprechbare Clips, **DubStage** nimmt deine Stimme auf und spielt die Szene am Stück damit ab.

*English version: `README_EN.md`*

<img src="docs/dubforge.png" alt="DubForge: Wellenform mit erkannten Clips und Untertiteln" width="900">

<img src="docs/dubstage-record.png" alt="DubStage: Aufnahme einer Zeile, der eigene Take live über dem Original" width="900">

<sub>Bildmaterial: <i>Tears of Steel</i> — (CC) Blender Foundation | <a href="https://mango.blender.org">mango.blender.org</a>, CC BY 3.0. Untertitel von der eingebauten Spracherkennung in DubForge erzeugt. Die Screenshots zeigen die englische Oberfläche.</sub>

## Automatische Untertitel

Die optionale Spracherkennung im Setup (oder in `Setup.bat`) auswählen, alternativ mit
`py -m pip install -r requirements-transcription.txt`. Nach der Analyse den Code
der gesprochenen Sprache eingeben (`fr` Franzoesisch, `en` Englisch, `de` Deutsch;
weitere Whisper-Sprachcodes sind moeglich) und **Untertitel generieren** anklicken.
Die gesprochene Sprache wird getrennt von der Oberflaechensprache gespeichert.

Standard ist das mehrsprachige Modell `large-v3` fuer hohe Genauigkeit auf der
CPU. `turbo` und `small` sind schnellere Alternativen. Bei erster Nutzung wird
das Modell heruntergeladen (mehrere GB fuer large-v3). Danach funktioniert es
aus dem Cache offline; Audio wird nie hochgeladen. Auf der CPU kann die
Verarbeitung mehrere Minuten oder laenger dauern. Optionales `cuda` braucht
eine kompatible NVIDIA-GPU, CUDA 12 cuBLAS und cuDNN 9; Details stehen in der
[faster-whisper-Anleitung](https://github.com/SYSTRAN/faster-whisper).

Text im vorhandenen Untertitelfeld pruefen und korrigieren. Standardmaessig
werden nur leere Felder gefuellt; **Vorhandene ersetzen** regeneriert auch
bestehenden Text. Zeitkorrekturen ordnen generierte Woerter neu zu und erhalten
manuelle Korrekturen. Erneute Erkennung behaelt manuell korrigierte Clips bei.
Bei Fehlern bleiben bestehende Untertitel erhalten.

DubStage-Videopacks erhalten zusaetzlich `dub_video.srt` und `dub_video.vtt` mit
dem gesamten Originalton-Transkript, auch ausserhalb der Clips. Manuelle
Clip-Korrekturen aendern nur `_captions.json`; SRT/VTT bei Bedarf separat
bearbeiten. Es gibt keine Uebersetzung und keine eingebrannten Untertitel.

Vorhandene Packs: `py caption_pack.py packs/Test --language fr`.
Optionen: `--model large-v3|turbo|small`, `--device cpu|cuda`, `--overwrite`.
Bestehender Text bleibt ohne `--overwrite` erhalten. Ersetzte Ausgabedateien
werden im Pack unter `_caption_backup_*` gesichert. Video, Audio und Clipnamen
bleiben unveraendert. Clips ohne zugeordnete Sprache werden gemeldet.

---

## Einmalig einrichten

1. **`DubStage-Setup-<Version>.exe`** von der [Release-Seite](https://github.com/xmrius/dubstage/releases/latest) laden
2. Ausführen — ohne Adminrechte, ein eigenes Python ist nicht nötig

Das Setup bringt sein eigenes Python mit allen Paketen mit, lädt ffmpeg und bietet zwei optionale Teile an: Demucs für die Stimmen-Trennung (zieht PyTorch nach, bis ~2 GB — ohne läuft alles weiter, nur ohne Backing-Track) und die Spracherkennung für automatische Untertitel. Außerdem lädt es `cloudflared` (ca. 55 MB, vorausgewählt), damit Freunde im Mehrspieler ohne Portfreigabe beitreten können. Alles lässt sich später durch erneutes Ausführen des Setups nachinstallieren.

Danach **DubForge** zum Bauen und **DubStage** zum Einsprechen starten — aus dem Startmenü oder vom Desktop.

*Ohne Installer:* alle Dateien in einen Ordner legen, **`Setup.bat`** doppelklicken (braucht Python 3.9+), dann **`Start DubForge.bat`** und **`Start DubStage.bat`**.

---

## Sprache umstellen

Oben rechts im Fenster: **Deutsch / English**. Wirkt sofort — Beschriftungen, Meldungen, Dialoge und Fehlertexte. Eingaben bleiben erhalten. Die Wahl wird gemerkt.

---

# DubForge — Packs bauen

**1. Quelle**

Entweder YouTube-Link einfügen oder eine lokale Datei wählen (MP4, MKV, MOV, WEBM, auch reine Audiodateien). Bei „Von" und „Bis" die Zeitspanne eintragen — `1:30`, `0:02:15.5` oder einfach `95` für Sekunden. Leer lassen = alles.

Dann **„Laden und analysieren"**. Das Tool lädt bzw. schneidet, extrahiert den Ton, trennt die Stimmen von Musik und Geräuschen und sucht selbst die Sprechabschnitte.

**2. Clips prüfen**

Die Wellenform zeigt die gefundenen Clips als Kästen.

| Aktion | Wie |
|---|---|
| Clip anhören | Doppelklick auf den Kasten |
| Clip auswählen | einfacher Klick |
| Anfang/Ende verschieben | Rand des Kastens ziehen |
| Neuen Clip anlegen | in leerem Bereich aufziehen |
| Umbenennen | Doppelklick in der Liste |
| Zoomen | Mausrad über der Wellenform |

Zu viele oder zu wenige Clips? **Empfindlichkeit** verstellen und **„Neu erkennen"**. Zu lange Clips? **Max. Cliplänge** runter und neu erkennen.

**Untertitel:** Unter der Liste gibt es ein Feld dafür. Clip anklicken, Text tippen, **Enter** — das speichert und springt gleich zum nächsten Clip. So arbeitest du dich ohne Mausklicks durch. DubStage zeigt den Text später groß unter dem Video an. Freiwillig: Clips ohne Untertitel funktionieren normal.

**3. Bauen**

Pack-Name eintragen, Häkchen bei **„Mit Video"** setzen (nötig für DubStage), dann **„Pack bauen"**. Der Pack landet im Ordner `packs` neben dem Tool — genau dort sucht DubStage. Über **„In Zielordner kopieren"** kannst du ihn zusätzlich woandershin legen.

## Was im Pack landet

| Datei | Wofür |
|---|---|
| `01_Name_44-048.wav` | Ein Clip. Die Zahl hinten ist der Startzeitpunkt im Video (44,048 s) |
| `dub_video.mp4` | Das Video zur Szene |
| `_backing_track.wav` | Musik und Geräusche ohne Stimmen |
| `_captions.json` | Die Untertitel, nach Clip-Dateiname |
| `_TIMESTAMPS.txt` | Übersicht aller Startzeiten samt Untertitel |
| `_README.txt` | Kurzinfo |

Alle Clips werden laut normalisiert (Peak −1 dBFS), damit beim Vergleich nicht die Lautstärke stört.

---

# DubStage — einsprechen

Pack auswählen → **Loslegen**. Pro Zeile:

| Knopf | Was passiert |
|---|---|
| **▶ Original** | Das Videostück läuft mit der Originalzeile |
| **● Aufnehmen** | 3-2-1, dann läuft dasselbe Stück und du sprichst drüber |
| **▶ Meine Aufnahme** | Deine Aufnahme direkt anhören, zum Video |
| **Zeile leer lassen** | Aufnahme verwerfen, die Zeile behält das Original |
| **‹ Zurück / Weiter ›** | Zeile wechseln |

Unter dem Video steht groß der **Untertitel** der Zeile. Die Leiste darüber zeigt alle Zeilen: grün = aufgenommen, gelb = wo du gerade bist. Direkt anklickbar, um zu springen.

Nach der letzten Zeile führt **Fertig** ins Finale: die ganze Szene läuft mit deiner Stimme, der Untertitel läuft mit. **Als Video speichern** legt eine MP4 im Ordner `dubs` ab. **‹ Zurück zu den Zeilen** geht jederzeit wieder rein.

Tastatur: **Leertaste** nimmt auf bzw. startet das Finale, **Esc** geht zurück.

## Der Vergleichsstreifen

Über der Knopfreihe liegt das eigentliche Werkzeug: die **Originalspur als blaue Silhouette**, darüber halbtransparent **deine Aufnahme** — beim Aufnehmen rot und live mitwachsend, danach grün. Eine goldene Marke zeigt, wo du gerade bist.

Beide Kurven teilen sich dieselbe Zeitachse, die bei Null des Clips beginnt. Damit siehst du auf einen Blick, ob du zu früh oder zu spät einsetzt und ob deine Pausen sitzen: liegen die Blöcke übereinander, passt das Timing. Der Streifen ist etwas breiter als das Original, weil nach dem Clip noch 0,7 Sekunden weiter aufgenommen wird — Platz, um den Satz zu Ende zu sprechen.

Beide Kurven werden auf ihre eigene Lautstärke normiert, verglichen wird also Rhythmus und nicht Pegel. Ist deine Aufnahme zu leise, steht das als Hinweis rechts unten.

Browser-Gäste im Koop-Spiel bekommen denselben Streifen.

## Mikrofon

Im Menü gibt es **Testen**: zwei Sekunden aufnehmen, Pegel ablesen, Wiedergabe. Falls nichts ankommt, im Auswahlfeld daneben ein anderes Gerät nehmen.

Standardmäßig nimmt DubStage das **Windows-Standard**-Mikrofon (erster Eintrag, mit dem Namen des Geräts). Gemerkt wird nur ein Mikrofon, das du selbst auswählst. Browser-Spieler wählen ihres in der Lobby oder unter den Aufnahmeknöpfen.

## Bildrate

Standard sind **25 Bilder pro Sekunde** bei 960 px Breite. Das Video wird dafür einmalig in Einzelbilder zerlegt und unter `%TEMP%\dubstage_cache` abgelegt, rund 37 MB pro Minute Video.

Falls dein Rechner ruckelt oder der Platz knapp wird, in `dubstage_settings.json` ändern:

```json
"video_fps": 20
```

Erlaubt sind 8 bis 30. Die Bilder werden beim nächsten Öffnen des Packs neu erzeugt.

## Packs, die nicht auftauchen

Gesucht wird im Ordner `packs` neben den Tools. Über **Hinzufügen … → Ordner mit Packs** lässt sich jeder weitere Ordner dauerhaft mit durchsuchen. Gefunden werden Packs darin, eine Ebene tiefer (wie im Ordner eines entpackten Zips) oder der Ordner selbst, wenn er ein Pack ist.

**Zip- und RAR-Packs** muss man nicht entpacken. Die `.zip` oder `.rar` nach `packs` oder in einen hinzugefügten Ordner legen oder direkt über **Hinzufügen … → Zip oder RAR** wählen. DubStage schaut hinein, entpackt Archive mit einem `dub_video` einmalig nach `packs\_archives` (im Hintergrund, das Menü zeigt es an) und listet sie wie jedes andere Pack. Andere Archive im selben Ordner (Programme, Shader …) bleiben unberührt. Liegt neben einem Zip ein gleichnamiger Ordner, gilt es als schon entpackt. RAR nutzt das `tar` von Windows 10/11; WinRAR oder 7-Zip gehen auch, falls installiert.

Damit ein Ordner als Pack zählt, braucht er ein **`dub_video`** (mp4, ogv, mkv, webm, mov oder avi) und mindestens einen Clip mit Zeitstempel im Dateinamen.

**Choicer-Voicer-Packs** laufen unverändert: den Download (z. B. `pennywise_vs_groot.zip`) nach `packs` legen oder das Zip bzw. seinen entpackten Ordner hinzufügen. DubStage liest Startzeiten, Figuren und Untertitel aus der `.txt` neben jedem Clip und den Titel aus `_pack_info.ini`. Im Mehrspieler verteilt *Automatisch aufteilen* ganze Figuren.

---

## Mit Freunden spielen (Koop)

Eine Szene gemeinsam vertonen: Der Host verteilt die Zeilen, jeder nimmt seine
Zeilen am eigenen Rechner auf, und jede Aufnahme geht automatisch an die
anderen. Am Ende hat jeder die ganze Szene mit allen Stimmen.

**Hosten:** Pack wählen → **Spiel hosten** → Namen eingeben. Die Lobby zeigt
einen **Raumcode** und die Adresse(n) für deine Freunde. Wer beitritt, bekommt
den Pack automatisch von dir, also nur Material teilen, das du teilen darfst.

So erreichen dich deine Freunde, eins davon reicht:

| Weg | Was zu tun ist |
|---|---|
| **Cloudflare Quick Tunnel** (am einfachsten) | Das Setup installiert `cloudflared` (sonst `winget install Cloudflare.cloudflared` oder `cloudflared.exe` nach `tools\` legen). Dann **Cloudflare Quick Tunnel starten** anhaken. Die `…trycloudflare.com`-Adresse schicken. Kein Router nötig. |
| **VPN** (Tailscale, ZeroTier, Radmin VPN) | Alle im selben VPN; deine VPN-IP mit Port schicken, z. B. `100.64.1.2:47800`. |
| **Portfreigabe** | TCP-Port 47800 (oder den gewählten) im Router auf deinen PC freigeben und deine öffentliche IP schicken, z. B. `203.0.113.5:47800`. |
| **Gleiches Netz** | Die LAN-Adresse aus der Lobby schicken. |

Fragt Windows, ob Python das Netzwerk nutzen darf: **Zulassen** klicken. Das
braucht es für VPN, LAN und Portfreigabe. Der Tunnel geht auch ohne.

**Beitreten:** **Beitreten** → Adresse einfügen, Raumcode und Namen eingeben.

**Im Browser beitreten (ohne Installation):** Mit Tunnel zeigt die Lobby zusätzlich einen **Browser-Link**, in dem der Raumcode schon steckt. Freunde öffnen ihn in Chrome, Edge oder Firefox, geben einen Namen ein und erlauben das Mikrofon. Sie können ihre Zeilen mit demselben Vergleichsstreifen wie in der App aufnehmen, alle Aufnahmen anhören und das Finale ansehen (als Video speichern geht nur in der App). Die Seite füllt das ganze Fenster. Browser erlauben das Mikrofon nur über https – Browser-Gäste brauchen also den Tunnel-Link, reine IP-Adressen gehen nur mit der App. Beim ersten Hosten eines Packs wandelt DubStage dessen Video im Hintergrund in ein leichtes MP4 für Browser um.

**Lobby:** Rechts steht, wer was spricht, nach Figuren gruppiert (der Name in
den Clip-Dateinamen). Alle Rollen sind anfangs frei. Jeder, ob in der App oder
im Browser, klickt eine freie Rolle an, um sie zu nehmen, und die eigene, um
sie wieder abzugeben. Rollen anderer lassen sich nicht wegnehmen. Der Host hat
das letzte Wort: Ein Klick reicht die Rolle reihum weiter (frei → jeder
Spieler). **Automatisch aufteilen** verteilt nur die noch freien Rollen und
lässt die gewählten in Ruhe. **Nach Zeilen** zeigt einzelne Zeilen. **Los
geht's** geht, sobald alle den Pack haben. Danach steht die Verteilung fest;
Zeilen, die niemand genommen hat, behalten die Originalstimme.

**Aufnehmen:** Aufnehmen kannst du nur deine eigenen Zeilen. Die Leiste über
dem Untertitel zeigt jede Zeile in der Farbe ihres Sprechers, hell, sobald sie
aufgenommen ist. Fremde Zeilen kannst du anhören, sobald die Aufnahme da ist.
Unten steht, wessen Zeilen noch fehlen. **Weiter** und **Zurück** springen
zwischen deinen eigenen Zeilen; jede andere Zeile erreichst du per Klick in der
Leiste. Der Host kann alle zurück in die **Lobby** holen und neu verteilen;
Aufnahmen bleiben erhalten.

**Hintergrund-Lautstärke:** Jeder Spieler hat einen Regler **Hintergrund**
(0–150 %) auf der Bühne, im Warteraum und im Finale. Er regelt den Backing
Track (Musik und Effekte; ohne Backing Track den Originalton des Videos) lauter
oder leiser, während er läuft, auch beim Aufnehmen – und nur für dich: Andere
Spieler und deine gesendeten Aufnahmen bleiben unberührt. Leiser vor dem
Aufnehmen heißt weniger Hintergrund im Mikrofon. Als Video speichern nimmt
deine Einstellung. App und Browser merken sie sich.

**Bereit und das Finale:** Auf der letzten Zeile heißt der Knopf **Bereit ✓**.
Er führt in einen Warteraum, der zeigt, wie weit alle sind (aufgenommene von
den eigenen Zeilen, bereit oder nimmt noch auf). **Meine Zeilen abspielen**
spielt deine Aufnahmen zum Video, **Zurück zu meinen Zeilen** nimmt das Bereit
zurück, damit du alles nochmal aufnehmen kannst. Sind alle bereit, holt jeder
alle Aufnahmen und das Finale mit der ganzen Szene öffnet sich. Ab dann sind
die Aufnahmen fest, und jeder kann die Szene abspielen oder als Video
speichern. Der Host hat **Jetzt fertigstellen**, falls jemand weg ist.

Geht jemand in der Lobby, werden seine Rollen wieder frei; im laufenden Spiel
übernimmt der Host. Beendet der Host, ist das
Spiel für alle vorbei.

---

## Updates

Beide Werkzeuge fragen beim Start bei GitHub nach, ob es eine neuere Fassung
gibt — höchstens alle sechs Stunden. Wenn ja, erscheint oben ein Banner: es
nennt die Version, **Was ist neu** klappt den Changelog dieser Version auf, und
**Jetzt aktualisieren** spielt sie ein. Das Archiv wird geladen und geprüft, die
App schließt sich, die Dateien werden getauscht und die App startet neu — dauert
ein paar Sekunden.

`packs/`, `dubs/`, `tools/` und die Einstellungen werden dabei nie angefasst. Es
werden nur die Programmdateien ersetzt, und die alten landen vorher in einem
Sicherungsordner unter `%TEMP%`, mit einem Protokoll daneben.

Netzzugriffe umfassen auch angeforderte Video-Downloads und das erstmalige
Herunterladen eines Spracherkennungsmodells. Audio wird nie hochgeladen.
Update-Pruefungen lassen sich abschalten mit `"check_updates": false` in
`dubforge_settings.json` oder `dubstage_settings.json`.

---

## Wenn etwas klemmt

**SmartScreen warnt vor dem Setup** — Es ist nicht signiert. *Weitere Informationen → Trotzdem ausführen*.

**Windows blockiert die BAT-Dateien** — Rechtsklick → Eigenschaften → unten **Zulassen**. Oder in PowerShell im Ordner: `Get-ChildItem -Recurse | Unblock-File`. Wichtig: die Dateien vorher aus dem Download-Ordner in einen normalen Ordner verschieben.

**„ffmpeg nicht gefunden"** — Das Setup (oder Setup.bat) nochmal laufen lassen. Klappt das nicht: bei `gyan.dev/ffmpeg/builds` die **release full** ziehen und `ffmpeg.exe`, `ffprobe.exe`, `ffplay.exe` aus `bin` in `tools\` legen.

**YouTube-Download schlägt fehl** — Fast immer ist yt-dlp veraltet. YouTube ändert ständig etwas an der Auslieferung, deshalb hält das Werkzeug nur wenige Wochen. In DubForge oben rechts auf **yt-dlp aktualisieren** klicken; die Version samt Alter steht beim Start im Protokoll. Von Hand geht es im Terminal mit `py -m pip install --upgrade yt-dlp`.

**Demucs bricht ab** — Kein Beinbruch, das Tool schaltet automatisch auf den Originalton um. Dann fehlt nur der Backing-Track.

**Clips sitzen leicht daneben** — Bei YouTube-Downloads kann der Schnitt am Keyframe hängen. Zeitspanne ein paar Sekunden großzügiger setzen und im Editor nachjustieren.

**Mikrofon nimmt nichts auf** — Im DubStage-Menü ein anderes Gerät wählen und **Testen** drücken.

---

Beim Material bist du selbst dafür verantwortlich, nur zu verwenden, wozu du berechtigt bist.

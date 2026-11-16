# Lies

Sprachen lernen mit Nachrichten: RSS abonnieren, Wörter antippen und Übersetzungen samt Satz automatisch sammeln.

## Docker (empfohlen)

Voraussetzung: Docker Engine mit Docker Compose v2. Das Image enthält die gesamte App, Python und SQLite; auf dem Host ist kein Python nötig.

```sh
git pull --ff-only origin feat/lies-prototype
docker compose up -d --build
```

Danach am Handy im VPN `http://<VPN-IP-des-Servers>:18086` öffnen. Standardmäßig wird Host-Port **18086** auf Container-Port **8000** veröffentlicht. Der bisherige Python-Server darf diesen Host-Port nicht gleichzeitig verwenden. Einen laufenden alten Server vorher mit `Strg+C` bzw. über dessen Dienstverwaltung beenden.

Für einen anderen Port oder nur die VPN-Schnittstelle:

```sh
cp .env.example .env
# In .env LIES_PORT und optional LIES_BIND auf die VPN-IP setzen.
docker compose up -d --build
```

Die App läuft im Container als Benutzer ohne Root-Rechte. Der Healthcheck prüft die lokale HTTP-API. Mit `docker compose ps` siehst du den Status, mit `docker compose logs -f lies` die Logs. Der Container startet nach einem Neustart des Docker-Diensts automatisch wieder (`unless-stopped`). Die App hat weiterhin keinen Login; den veröffentlichten Port nur im eigenen Netz/VPN zugänglich machen.

### Vorhandene Abos und Vokabeln übernehmen

Docker verwendet ein eigenes persistentes Volume `lies-data` (mit Compose-Projektpräfix) für `/app/data`. Deine bisherige Datei `./data/lies.sqlite3` wird **nicht automatisch importiert**. Für den ersten Umstieg: alten Python-Server vollständig stoppen, bevor du die Datenbank übernimmst. Vor dem ersten `up`:

```sh
docker compose build
docker compose run --rm --no-deps \
  --volume "$PWD/data:/import:ro" lies python -c '
from pathlib import Path
import sqlite3
source = Path("/import/lies.sqlite3")
target = Path("/app/data/lies.sqlite3")
if not source.is_file():
    raise SystemExit("Keine alte Datenbank gefunden.")
if target.exists():
    raise SystemExit("Zieldatenbank existiert bereits; Import abgebrochen.")
with sqlite3.connect("file:/import/lies.sqlite3?mode=ro", uri=True) as old:
    with sqlite3.connect(target) as new:
        old.backup(new)
print("Abos und Vokabeln übernommen.")
'
docker compose up -d
```

Der Import überschreibt keine vorhandene Docker-Datenbank. Falls du Docker schon gestartet hast, bleibt die darin angelegte Datenbank erhalten; importiere dann nicht über diese Datei. Deine ursprüngliche lokale Datenbank bleibt unverändert.

### Aktualisieren, stoppen und sichern

```sh
git pull --ff-only origin feat/lies-prototype
docker compose up -d --build
# Stoppen; Daten bleiben erhalten:
docker compose down
```

Das Volume bleibt beim Neuaufbau oder Ersetzen des Containers erhalten. **`docker compose down --volumes` löscht die Docker-Daten dauerhaft.**

Konsistentes SQLite-Backup bei laufendem Container erstellen:

```sh
docker compose exec -T lies python -c 'import sqlite3; source=sqlite3.connect("/app/data/lies.sqlite3"); target=sqlite3.connect("/app/data/backup.sqlite3"); source.backup(target); target.close(); source.close()'
docker compose cp lies:/app/data/backup.sqlite3 ./lies-backup.sqlite3
```

Alternativ ohne Compose:

```sh
docker build -t lies:local .
docker volume create lies-data
docker run -d --name lies --restart unless-stopped \
  -p 18086:8000 -v lies-data:/app/data lies:local
```

## Starten und aktualisieren (ohne Docker)

Python 3.11+; für die App sind keine Pakete oder API-Schlüssel nötig.

```sh
python3 server.py
# Alternativer Port, z.B. für den Zugriff über dein VPN:
PORT=18086 python3 server.py
```

Öffne http://127.0.0.1:8000 bzw. auf deinem Handy `http://<VPN-IP-des-Servers>:18086`. Der Server lauscht auf allen Schnittstellen (`0.0.0.0`); Zugriff per Firewall auf das eigene Netz/VPN beschränken. Einzelbenutzer-Testversion ohne Login.

Updates auf dem bisherigen Testbranch:

```sh
git pull --ff-only origin feat/lies-prototype
```

Danach den laufenden Python-Prozess neu starten und die Seite neu laden. SQLite liegt unter `data/lies.sqlite3`; Abos und Vokabeln bleiben erhalten. Die neue Spalte für Übersetzungsalternativen wird automatisch hinzugefügt. Alte Einträge bleiben sichtbar und werden beim nächsten Antippen um Alternativen ergänzt, sofern der Dienst erreichbar ist.

## Nachrichten und Artikeltexte

RSS direkt von BBC, The Guardian, tagesschau, France 24, El País, ANSA und **NOS Nieuws (Niederländisch)**. Eigene öffentliche HTTPS-RSS-/Atom-Feeds können ergänzt werden.

Viele Feeds liefern nur einen Titel und eine Zusammenfassung. Mit **„Artikeltext hier laden“** ruft Lies die öffentliche Originalseite ab und extrahiert den lesbaren Text aus Artikelabsätzen oder strukturierten Artikeldaten. Auch in diesem Text lassen sich Wörter antippen. Es werden keine fremden Skripte ausgeführt. Die App prüft den Link gegen die Beiträge des abonnierten Feeds.

Die Extraktion funktioniert je nach Website unterschiedlich: JavaScript-Seiten, Zugangsbeschränkungen, Bezahlschranken oder fehlende Artikelstruktur können das Nachladen verhindern. Dann bleibt der Feed-Auszug sichtbar und der Original-Link verfügbar. Als kostenpflichtig markierte strukturierte Artikel werden abgelehnt; keine Paywalls werden umgangen. Eine erfolgreiche Extraktion garantiert nicht, dass alle Absätze der Website enthalten sind.

Abrufe prüfen DNS und Weiterleitungen gegen private/lokale Adressen, begrenzen Antwortgröße und Laufzeit. Feedtexte werden fünf Minuten, geladene Originaltexte bis zu 30 Minuten im Arbeitsspeicher gecacht.

## Wörterbücher und mehrere Übersetzungen

- Für **englische Wörter** verwendet Lies die kostenlosen öffentlichen Übersetzungstabellen von [Wiktionary](https://en.wiktionary.org/). Verfügbare Übersetzungen werden nach Bedeutung angezeigt; die kurzen Bedeutungsangaben stammen auf Englisch aus dem Wörterbuch. Beispielsweise liefert „human“ unter anderem „menschlich“ und „Mensch“. Die Quelle wird pro Eintrag verlinkt. Wiktionary-Texte stammen von den jeweiligen Mitwirkenden und stehen unter [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/); diese Lizenz gilt auch für daraus übernommene Wörterbuchdaten im Export.
- Bei anderen Ausgangssprachen oder fehlenden Wörterbuchtreffern: [MyMemory](https://mymemory.translated.net/doc/spec.php), öffentlich ohne Schlüssel mit kostenlosem Tageskontingent (laut Dokumentation 5.000 Zeichen ohne E-Mail). Zusätzlich zur Hauptübersetzung zeigt Lies Treffer für genau dasselbe Wort an; unscharfe Treffer für andere Sätze werden ausgeschlossen. MyMemory ist ein Übersetzungsdienst, kein redaktionell geprüftes Wörterbuch. Nicht jeder Begriff hat mehrere verfügbare Treffer.
- Nur Wort und Sprachpaar werden an diese Dienste übertragen, nicht der Satz. Alternativen werden gemeinsam mit Satz, Quelle, Datum und Sprachpaar in SQLite gespeichert und lokal wiederverwendet. Neue fehlgeschlagene Übersetzungen erzeugen keinen Eintrag. Bestehende Wörter bleiben bei Dienstausfällen erhalten.
- Die Alternativen sind keine vollständige Liste aller Bedeutungen. Die passende Übersetzung hängt vom Satz ab; eine automatische Auswahl nach Kontext erfolgt noch nicht.

## Separate Vokabellisten

Deutsch, Englisch, Französisch, Spanisch, Italienisch, Portugiesisch und **Niederländisch** sind als Lern- und Übersetzungssprachen verfügbar.

Unter **Wortschatz → Vokabelliste** wählst du eine eigene Liste je Lernsprache. Zähler, Löschen und JSON-Export beziehen sich auf diese Liste. Der Export enthält alle gespeicherten Alternativen und die Artikelquelle. Gleiche Wörter im selben Sprachpaar werden aktualisiert statt doppelt angelegt; Wörter aus anderen Sprachen bleiben getrennt. Die Daten bleiben gemeinsam in einer SQLite-Datei, die Listen werden nach Ausgangssprache getrennt angezeigt.

## Prüfen

```sh
python3 -m unittest discover -s tests -v
node --check static/app.js
```

19 Tests für RSS/Atom, Artikel-Extraktion und Fallbacks, Übersetzungsalternativen, Bestandsmigration, Speicherung, Dienstfehler und URL-Prüfung. Sie verwenden lokale Testdaten und benötigen keine externen Dienste. GitHub Actions führt diese Prüfungen ebenfalls aus.

Optionaler mobiler Browsercheck mit Playwright und Chromium:

```sh
pip install playwright
playwright install chromium
python3 tests/browser_smoke.py
```

Der Browsercheck startet einen temporären lokalen HTTP-Server und verwendet simulierte externe Dienste. Er prüft RSS-Lesen, Artikel-Nachladen und Ausfall-Fallback, Übersetzungsalternativen, Speicherung, getrennte Sprachlisten, niederländische Wörter und den Export der gewählten Liste.

Docker-Build, HTTP-Erreichbarkeit, Healthcheck, Non-Root-Benutzer und Datenerhalt nach Container-Neuerstellung prüfen: `python3 tests/docker_smoke.py`. Der Test verwendet ein eigenes temporäres Compose-Projekt und löscht nur dessen Container/Volume.

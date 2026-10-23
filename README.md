# Lies

Sprachen lernen mit Nachrichten: RSS abonnieren, Wörter antippen und Übersetzungen samt Satz automatisch sammeln.

## Starten und aktualisieren

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

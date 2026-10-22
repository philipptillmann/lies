# Lies

Sprachen lernen mit Nachrichten: RSS abonnieren, Wörter antippen und Übersetzungen samt Satz automatisch sammeln.

## Lokal starten

Python 3.11+; keine Pakete oder API-Schlüssel nötig.

```sh
python3 server.py
```

Öffne http://127.0.0.1:8000. Tests: `python3 -m unittest discover -s tests -v`.

SQLite liegt unter `data/lies.sqlite3`. Abos und Vokabeln bleiben nach Neustarts erhalten. Diese Testversion ist für eine einzelne Person und den lokalen Betrieb gedacht; kein Login oder Mehrbenutzerbetrieb. Nicht ungeschützt öffentlich bereitstellen.

## Kostenlose Quellen

- RSS direkt von BBC, The Guardian, tagesschau, France 24, El País und ANSA. Feedtexte können gekürzt sein; der Originalartikel wird verlinkt. Keine Paywalls werden umgangen.
- Übersetzungen: [MyMemory](https://mymemory.translated.net/doc/spec.php), öffentlich ohne Schlüssel, derzeit 5.000 Zeichen pro Tag ohne E-Mail. Dienstkontingente und Verfügbarkeit können sich ändern. Nur das angeklickte Wort und das Sprachpaar werden übertragen, nicht der Satz. Übersetzungen sind maschinell bzw. aus Translation Memories und können ungenau sein; kein redaktionell geprüftes Wörterbuch. Die UI verlinkt zusätzlich zum kostenlosen Wiktionary.
- Übersetzungen werden lokal zwischengespeichert. Fehler und Kontingentüberschreitungen erzeugen keine falschen Vokabeln.

## Umfang

Deutsch, Englisch, Französisch, Spanisch, Italienisch und Portugiesisch als Lern- und Übersetzungssprachen. Eigene öffentliche HTTPS-RSS-/Atom-Feeds. Abos lassen sich entfernen, Vokabeln löschen und als JSON exportieren. Wörter werden zusammen mit Satz, Quelle, Sprachpaar und Datum gespeichert. Gleiche Wörter im selben Sprachpaar werden aktualisiert statt doppelt angelegt.

RSS-Abrufe prüfen DNS und Redirects gegen lokale/private Adressen, begrenzen Größe und Laufzeit und cachen Ergebnisse fünf Minuten. Die Tests prüfen Parser, Speicherung, Übersetzungsfehler und URL-Schutz ohne externe Dienste.

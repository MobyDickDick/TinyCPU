# Vorschlag: symbolischer TinyCPU-Debugger

Dieses Dokument trifft die im Hardware-Arbeitsplan geforderte Produktentscheidung
für die Weiterentwicklung nach TinyCPU 1.0. Von den dort genannten Kandidaten
wird **Entwicklungswerkzeuge** ausgewählt. Das erste neue Arbeitspaket erhält die
Nummer **AP 16** und ergänzt einen symbolischen Debugger auf dem bestehenden
Maschinenformat `tinycpu-machine-v1`.

Die Auswahl verändert weder die abgenommene 16/12-Bit-Hardware noch die
TinyCPU-1.x-Schnittstellen. Zusätzliche Hardwareprofile sowie ein Bus- oder
Interrupt-Modell bleiben ausdrücklich außerhalb dieses Pakets.

## Ziel und Benutzersicht

AP 16 soll ein Programm deterministisch anhalten und seinen Zustand anzeigen
können. Der minimale Bedienumfang besteht aus:

- Laden eines vorhandenen TinyCPU-Programms über denselben Assemblerpfad wie
  der Simulator;
- Setzen und Löschen von Breakpoints anhand einer Instruktionsadresse oder
  eines Quelllabels;
- `continue` bis zum nächsten Breakpoint, Halt oder Fehler sowie `step` für
  exakt eine Instruktion;
- Anzeige von PC, Akkumulator samt Validität, Adressregister samt Validität,
  Zero/Negative, den sechs Sticky-Fehlerflags und veränderten Speicherzellen;
- stabilem, maschinenlesbarem JSON für automatisierte Werkzeuge sowie einer
  für Menschen lesbaren Textausgabe.

Ein Breakpoint wird **vor** der Instruktion an seiner Adresse ausgelöst. `step`
führt von einem solchen angehaltenen Zustand genau diese Instruktion aus. Ein
bereits beendetes Programm darf nicht weiterlaufen und liefert seinen
unveränderten Endzustand. Diese Regeln vermeiden Mehrdeutigkeiten bei Sprüngen
und Fehlerhalten.

## Technische Grenze

Der Debugger ist zunächst ein Frontend des Python-Referenzmodells. Er liest
keine internen Logisim-Netze und verändert keine `.circ`-Datei. Seine
symbolische Zuordnung wird beim Assemblieren erzeugt und enthält für jede
ausgegebene Instruktionsadresse die Quellzeile und, falls vorhanden, das Label.
Die Zuordnung ist Debug-Metadatum und kein Bestandteil des 22-Bit-Worts.

Die Zustandsdarstellung verwendet die Architekturbegriffe aus
`tiny_cpu.md`. Speicher wird standardmäßig als Änderungsliste seit dem letzten
Stopp ausgegeben; eine gezielte Abfrage darf zusätzlich eine Adresse oder einen
geschlossenen Adressbereich lesen. Ungültige Werte werden immer zusammen mit
ihrem Validitätsbit dargestellt und niemals stillschweigend als gültige Null.

Nicht Bestandteil von AP 16 sind Source-Level-Ausdrucksauswertung, Watchpoints,
Rückwärtsausführung, ein Netzwerkprotokoll, eine IDE-Erweiterung und Änderungen
an Programm oder Speicher während eines Laufs.

## Kompatibilitätsfolgen

Die stabilen Grenzen von TinyCPU 1.x bleiben unverändert:

1. `tinycpu-machine-v1` behält Wortbreite, Opcode-Zuordnung und
   Operandencodierung.
2. Das 16/12-Bit-Hardwareprofil, die elektrische AP-12-Abnahme und die
   Releaseartefakte von 1.0 werden nicht neu geöffnet.
3. Bestehende Simulator- und Assembleraufrufe behalten Verhalten und Ausgabe.
4. Das neue Debug-JSON erhält vor seiner Veröffentlichung eine eigene
   `schema_version`; unbekannte Felder müssen von Konsumenten ignoriert werden.
5. Quelllabels sind Komfortmetadaten. Adress-Breakpoints funktionieren auch
   bei einem reinen ROM-Image ohne Quelldatei.

AP 16 darf deshalb als additive Funktion in einer späteren 1.x-Version
erscheinen. Eine Änderung am Maschinenwort oder an der Laufzeitsemantik würde
dagegen ein getrenntes, versionsbrechendes Arbeitspaket erfordern.

## Messbare Abnahme

AP 16 gilt erst als abgeschlossen, wenn alle folgenden Kriterien automatisiert
geprüft sind:

- Ein Countdown-Fixture stoppt vor dem Label der Schleife bei jedem Besuch;
  die beobachteten PCs entsprechen den Instruktionsadressen des Listings.
- Wiederholtes `step` erzeugt nach jeder Instruktion denselben vollständigen
  Architekturzustand wie ein normaler Lauf des Referenzmodells.
- `continue` endet eindeutig an Breakpoint, `HALT`, `HALT_ERROR` oder
  Schrittlimit und benennt den Grund im Text- und JSON-Modus.
- Mindestens je ein Test deckt ungültigen Akkumulator, ungültiges
  Adressregister, Speicherinvalidität und jedes der sechs Sticky-Fehlerbits ab.
- Breakpoints an unbekannten Labels und außerhalb des geladenen Programms
  werden vor dem Start mit einer eindeutigen Diagnose abgelehnt.
- Zwei identische Läufe liefern bytegleiches JSON; dessen Schema und Beispiele
  sind dokumentiert.
- Die bestehende TinyCPU-Verifikation sowie die elektrische 1.0-Abnahme bleiben
  unverändert erfolgreich.

## Umsetzungsreihenfolge

1. Versioniertes Debug-JSON und Stop-Gründe als Vertrag festlegen.
2. Assembler-Listing um die optionale Adresse-zu-Quelle-Zuordnung ergänzen.
3. Pausierbare Ausführung des Referenzmodells hinter einer eigenen
   Debugger-Schnittstelle kapseln.
4. Text- und JSON-CLI implementieren.
5. Zustandsparität, Breakpoints, Fehlerfälle und deterministische Ausgabe
   automatisiert abnehmen.

Diese Reihenfolge ist die Paketgrenze, nicht der Nachweis einer bereits
erfolgten Implementierung. Mit diesem Vorschlag sind Richtung,
Kompatibilitätsfolgen und Abnahmekriterien entschieden; die Implementierung von
AP 16 ist die nächste ausführbare Aufgabe.

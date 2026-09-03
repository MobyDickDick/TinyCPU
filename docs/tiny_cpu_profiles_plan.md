# Vorschlag: zweites TinyCPU-Hardwareprofil

**Status: in Umsetzung (Schritte 1 bis 3 abgeschlossen, Schritt 4 vorbereitet).** Dieses Dokument trifft die im Hardware-Arbeitsplan nach
AP 16 geforderte Produktentscheidung. Von den beiden verbliebenen Kandidaten
wird **Weitere Hardwareprofile** ausgewählt. Das neue Arbeitspaket erhält die
Nummer **AP 17**. Eine Bus-/Interrupt-Erweiterung bleibt ausdrücklich einem
späteren, getrennten Vorschlag vorbehalten.

## Zielprofil und Benutzersicht

AP 17 ergänzt das bestehende Profil `tinycpu-16-12` um genau ein kleineres
Lehrprofil **`tinycpu-8-8`** mit 8 Datenbits, 8 Adressbits und 256
Speicherzellen. Beide Profile verwenden weiterhin den vollständigen
symbolischen Befehlssatz. Assembler, VM und Verifikationswerkzeuge erhalten
eine explizite Profilauswahl; ohne Auswahl bleibt `tinycpu-16-12` der
unveränderte Standard.

Für das neue Profil werden eine eigene Logisim-Schaltung, ein
maschinenlesbarer Hardwarevertrag und profilbezogene ROM-Fixtures
eingecheckt. Ein Programm muss beim Assemblieren eindeutig abgelehnt werden,
wenn Konstanten, Adressen oder Offsets im gewählten Profil nicht darstellbar
sind. Werkzeuge dürfen Werte nicht stillschweigend abschneiden.

## Technische Grenze

Das 8/8-Profil ist eine eigenständige, elektrisch geprüfte Variante und keine
Parametrisierung der vorhandenen `.circ`-Datei zur Laufzeit. Gemeinsam genutzte
Python-Logik soll Breiten aus dem Profilvertrag beziehen; profilspezifische
Logisim-Artefakte und Referenztraces bleiben dagegen getrennt benannt. Das
verhindert, dass eine Anpassung für 8/8 die abgenommene 16/12-Schaltung
unbemerkt verändert.

Das Maschinenwort erhält für das neue Profil eine eigene Formatkennung. Der
6-Bit-Opcode bleibt identisch, der Operand ist 8 Bit breit; ein 8/8-Wort ist
damit 14 Bit breit. Listing, ROM-Image und Debug-Metadaten nennen Profil und
Formatkennung ausdrücklich. Eine automatische Konvertierung vorhandener
16/12-ROM-Dateien gehört nicht zu AP 17.

Nicht Bestandteil des Pakets sind frei wählbare Breiten, weitere Profile,
Änderungen am Befehlssatz, neue Peripherie, Interrupts, ein Busprotokoll sowie
die Veröffentlichung einer neuen Produktversion.

## Kompatibilitätsfolgen

1. `tinycpu-16-12`, `tinycpu-machine-v1` und die TinyCPU-1.0-Artefakte bleiben
   byte- und verhaltenskompatibel.
2. Bestehende CLI-Aufrufe ohne Profiloption verwenden weiterhin 16/12 und
   behalten Ausgabe, Fehlerverhalten und Exitcodes.
3. Das neue Maschinenformat bekommt eine eigene Kennung; 14- und 22-Bit-ROMs
   dürfen nicht allein anhand ihrer Dateiendung verwechselt werden.
4. Quellprogramme bleiben symbolisch portabel, sofern alle Operanden und
   Laufzeitwerte in beiden Profilen darstellbar sind. Binärprogramme sind nur
   innerhalb ihrer Formatkennung portabel.
5. Gemeinsame JSON-Ausgaben werden additiv um Profil- und Formatangaben
   ergänzt. Konsumenten der bestehenden Schemaversion müssen unbekannte Felder
   weiterhin ignorieren können.
6. Die elektrische AP-12-Abnahme und der Releasevertrag von 1.0 werden nicht
   ersetzt. Das 8/8-Profil benötigt einen eigenen vollständigen Nachweis.

## Messbare Abnahme

AP 17 gilt erst als abgeschlossen, wenn alle folgenden Kriterien automatisiert
geprüft sind:

- Ein versionierter 8/8-Vertrag legt Datenbreite, Adressbreite,
  Speichergröße, Maschinenformat und alle öffentlichen Schaltungspins fest.
- Assembler und Decoder führen alle 50 Opcodes im 14-Bit-Format im Roundtrip;
  Grenzwerte werden akzeptiert und jeder um eins zu große oder zu kleine
  Operand wird mit einer eindeutigen Diagnose abgelehnt.
- Ein profilportables Countdown-Programm erzeugt in VM und Logisim für 8/8
  denselben taktweisen Architekturzustand, dieselbe Ausgabe und denselben
  Haltgrund.
- Eine elektrische ISA-Matrix deckt im 8/8-Profil jeden Opcode sowie alle
  sechs Sticky-Fehlerbits ab und verhindert ungetestete Opcodes über
  Abdeckungsmetadaten.
- Adressüberlauf, vorzeichenbehafteter Datenüberlauf und Offset-Grenzen werden
  an den 8-Bit-Grenzen sowohl positiv als auch negativ getestet.
- Der symbolische Debugger zeigt Profil und Format an; Breakpoints,
  Einzelschritte und Zustandsparität funktionieren für dasselbe portable
  Fixture in beiden Profilen.
- Die unveränderte Offline- und elektrische 16/12-Abnahme bleibt erfolgreich.
  Ein profilspezifischer Fehler darf nicht durch Überspringen des jeweils
  anderen Gates verborgen werden.

## Umsetzungsreihenfolge

1. Profil- und Maschinenformatvertrag für 8/8 festlegen und gegen den
   bestehenden 16/12-Standard abgrenzen.
2. Assembler, VM, Debugger und Prüfer auf explizite Profilobjekte umstellen,
   wobei die bisherigen Standardaufrufe unverändert bleiben.
3. Die 8/8-Logisim-Schaltung und profilbezogene Countdown-Artefakte ergänzen.
4. Elektrischen Kerntrace und vollständige ISA-/Fehlermatrix für 8/8
   automatisieren.
5. Beide Profile gemeinsam regressionsprüfen und Bedienung,
   Kompatibilitätsgrenzen sowie Nachweisartefakte dokumentieren.

Diese Reihenfolge ist die Grenze des geplanten AP 17. Der Vorschlag legt
bewusst noch keine Implementierungsdetails fest, die erst durch die
elektrische Schaltung validiert werden können.

## Umsetzungsstand

Die Schritte 1 bis 3 sind umgesetzt. `tinycpu-8-8.json` und
`tinycpu-machine-8-v1.json` frieren Profil und 14-Bit-Format ein. Assembler,
ROM-Decoder, VM und Debugger verwenden ein gemeinsames explizites Profilobjekt;
ohne `--profile` bleibt `tinycpu-16-12` der Standard. Operanden werden vor der
Codierung profilbezogen geprüft statt abgeschnitten. Die Regression deckt alle
50 Opcodes im 14-Bit-Roundtrip, Daten-/Adressgrenzen, 8-Bit-Überlauf und den
portablen Countdown in beiden Referenzmodell-Profilen ab.

`TinyCPU-8-8.circ` ist die eigenständige, auf 8-Bit-Daten und -Adressen sowie
14-Bit-Instruktionswörter spezialisierte Logisim-Schaltung. Ihr eingebettetes
ROM entspricht bytegenau den profilbezogenen AP-17-Countdown-Artefakten. Der
Offline-Prüfer verwirft verbliebene 16/12-/22-Bit-Breiten, abweichende
ROM-Breiten und ein vom Fixture abweichendes eingebettetes Programm.

`tinycpu-electrical-matrix-8-v1.json` beschreibt jetzt alle 50 isolierten
Opcode-Fälle und die sechs Sticky-Fehler-Fixtures profilgerecht. Der
Offline-Prüfer assembliert jeden Fall ausdrücklich als `tinycpu-8-8`, prüft
Formatkennung, Rohwortbreite sowie Opcode- und Fehlerabdeckung und verhindert
damit insbesondere versehentlich übernommene 16-Bit-Grenzwerte.

AP 17 bleibt offen: Der reale elektrische Kerntrace und die Ausführung dieser
vollständigen Matrix im gepinnten Logisim-Simulator (restlicher Schritt 4) sind
noch nicht vorhanden. Entsprechend wird aus Matrixvertrag, struktureller
Schaltungsprüfung und Softwaretests noch kein elektrischer Nachweis abgeleitet.

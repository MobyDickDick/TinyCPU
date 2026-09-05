# Vorschlag: Peripherie und Integration

**Status: in Umsetzung (Interruptsteuerungsgrenze eingecheckt).** Dieses Dokument trifft die nach AP 17 noch offene
Produktentscheidung. Die Richtung **Peripherie und Integration** wird als
**AP 18** ausgewählt. Das Paket ergänzt genau einen speicherabgebildeten
Ausgabeport und eine externe, maskierbare Interruptquelle. Weitere Geräte und
ein allgemein erweiterbarer Systembus bleiben späteren Paketen vorbehalten.

## Ziel und Benutzersicht

AP 18 soll TinyCPU-Programme mit ihrer Umgebung verbinden, ohne bestehende
Programme oder das Verhalten der beiden abgeschlossenen Hardwareprofile zu
ändern. Dafür erhält zunächst ausschließlich `tinycpu-16-12` einen optionalen
Peripheriemodus mit:

- einem schreibbaren 16-Bit-Ausgaberegister;
- einer externen, flankengesteuerten Interruptanforderung;
- einem Interrupt-Maskenbit; und
- einer festen Interruptvektoradresse.

Der Ausgaberegisterzugriff erfolgt über eine reservierte Adresse. Ein
maskierter Interrupt bleibt ausstehend und wird nach dem Entmaskieren bedient.
Bei der Annahme sichert die CPU die Rückkehradresse in einem eigenen Register,
sperrt weitere Interrupts und springt zum Vektor. Eine neue Rückkehrinstruktion
stellt den Programmzähler und die vorherige Maske wieder her. Reset löscht
Ausgaberegister, Maske, ausstehende Anforderung und gesicherte Rückkehradresse.

Der Peripheriemodus ist in Werkzeugen und Schaltung ausdrücklich auszuwählen.
Ohne diese Auswahl bleiben Assemblierung, VM, Debugger und elektrische
Ausführung byte- und verhaltensgleich zum bestehenden `tinycpu-16-12`-Profil.

## Versionierte Verträge

Vor der Schaltungsänderung werden drei maschinenlesbare Grenzen eingefroren:

1. Ein Systemprofil benennt Basis-Hardwareprofil, reservierte I/O-Adresse,
   Registerbreiten, Resetwerte, Interruptvektor und Prioritätsregeln.
2. Eine neue Maschinenformatkennung erweitert die Opcode-Tabelle um Befehle
   zum Maskieren und zur Interrupt-Rückkehr. Bestehende Opcodewerte werden
   nicht umnummeriert.
3. Ein Trace-Schema ergänzt den Architekturzustand um Ausgaberegister,
   Interruptmaske, Pending-Bit und Rückkehradresse samt Validität.

Diese erste Umsetzungsstufe liegt nun als
`tinycpu-peripherals-16-12-v1.json`, `tinycpu-system-machine-v1.json` und
`tinycpu-system-trace-v1.json` vor. `tiny_cpu_systems.py` lädt die Verträge
nur nach expliziter Systemauswahl und prüft ihre Querverweise und Adressgrenzen.
Das eingefrorene Standardprofil und seine 50 Opcodes bleiben dabei unverändert.

Die Priorität an einer Taktflanke ist festgelegt: Reset vor angenommener
Interruptanforderung, angenommener Interrupt vor normalem Fetch. Gleichzeitig
eintreffende Anforderungen werden in einem Pending-Bit zusammengefasst. Ein
Interrupt wird nur zwischen zwei Instruktionen angenommen; es gibt keine
teilweise ausgeführte Instruktion.

Assembler, ROM-Decoder und Encoder verwenden das erweiterte Maschinenformat
nur bei expliziter Systemauswahl. Das Python-Referenzmodell bildet inzwischen
Ausgabeport, Flankenerkennung, Pending-Zustand, Maskierung, Annahme an der
Instruktionsgrenze und Interrupt-Rückkehr ab. Der Debugger gibt diese Zustände
unter der neuen Schemaversion aus; Aufrufe ohne Systemauswahl behalten ihr
bisheriges Format und Verhalten. Referenztests decken außerdem den
Vektorfehler, eine illegale Rückkehr und Reset der neuen Zustände ab.

## Technische Grenze

AP 18 baut eine eigenständige Logisim-Schaltung auf Basis der abgenommenen
16/12-Variante. Die Dateien von `tinycpu-16-12` und `tinycpu-8-8` werden nicht
zu einem dynamisch parametrierten Schaltplan zusammengeführt. Die Python-VM
modelliert denselben Taktvertrag und bleibt Referenz für elektrische Traces.

Die reservierte I/O-Adresse wird nicht zusätzlich als RAM-Zelle beschrieben.
Lesen von ihr liefert den letzten gültigen Ausgabewert; Schreiben übernimmt
Wert und Validität atomar. Alle übrigen Adressen behalten ihre bisherige
Speichersemantik. Die neue Interrupt-Rückkehr ist außerhalb eines aktiven
Handlers illegal und setzt das bestehende Sticky-Flag `ILL` mit Fehlerhalt.

Nicht Bestandteil sind DMA, verschachtelte oder priorisierte Interrupts,
mehrere Interruptquellen, Timer, serielle Protokolle, Eingabegeräte,
Bus-Arbitration, Wait States und eine Änderung des 8/8-Profils.

Die eigenständige Datei `TinyCPU-Peripherals.circ` friert nun außerdem die
elektrische Systemgrenze ein. Ihr Top-Level `TinyCPUSystemMain` exportiert die
Interruptanforderung und sämtliche zusätzlichen Trace-Zustände als direkte
Pins. Der Offline-Prüfer gleicht Richtung und Breite jedes Pins mit dem
Systemprofil ab. Die interne Verdrahtung des Ausgabeports und der
Interruptsteuerung sowie deren elektrische Abnahme bleiben die nächsten
Teilschritte von AP 18; die neue Datei wird daher noch nicht vom elektrischen
Release-Gate als fertige System-CPU behandelt.

Der erste interne Baustein `OutputPort` ist jetzt ebenfalls Bestandteil der
Schaltung. Zwei taktsynchrone Register übernehmen Wert und Validität gemeinsam
bei `WRITE_ENABLE`; `RESET` löscht beide Zustände. Sein maschinenlesbarer
Komponentenvertrag und der Offline-Prüfer sichern Pinrichtungen, Breiten und
die beiden getrennten Zustandsregister ab. Der neue Baustein
`OutputMemoryPath` friert jetzt auch die Speicherpfadgrenze ein: Er dekodiert
ausschließlich Adresse `0xfff`, trennt Port- und RAM-Schreibfreigabe und beschreibt die Auswahl von Wert und Validität beim Lesen.
Der Komponentenvertrag und der Offline-Prüfer sichern dabei Adress- und
Datenbreiten, die reservierte Adresse sowie die getrennten Lese- und
Schreibpfade ab. Der Baustein `InterruptController` friert zusätzlich die
elektrische Interruptsteuerungsgrenze ein: Seine Pins führen Flankenanforderung,
Instruktionsgrenze, Maskenbefehle, Rückkehrbefehl und nächsten PC sowie Annahme,
Sprungziel, sämtliche Interruptzustände und den Fehler einer illegalen
Rückkehr. Sechs getrennte Register besitzen Request-Pegel, Maske, Pending-Bit,
Handlerzustand und Rückkehradresse samt Validität; Vektor, Breiten und die
benannten Flanken-, Annahme- und Rückkehrpfade werden offline gegen den
Systemvertrag geprüft. Die funktionale Verdrahtung dieser Grenzen in die
vollständige CPU folgt weiterhin innerhalb von Schritt 3.

## Kompatibilitätsfolgen

1. TinyCPU 1.0, `tinycpu-machine-v1` und beide vorhandenen Hardwareprofile
   bleiben unverändert; AP 18 ist eine additive Zielvariante für eine spätere
   Produktversion.
2. Bestehende CLI-Aufrufe ohne Systemprofilauswahl verwenden weiterhin das
   bisherige Maschinenformat und akzeptieren die neuen Mnemonics nicht.
3. Programme für das neue Format dürfen nicht als bestehende 22-Bit-ROMs
   ausgegeben oder ohne Formatprüfung geladen werden.
4. Die reservierte I/O-Adresse ist nur im Peripheriemodus besonders. Im
   bisherigen Profil bleibt sie eine normale RAM-Adresse.
5. Debug- und Trace-JSON werden nur unter einer neuen Schemaversion um den
   Interruptzustand erweitert.
6. Die AP-12- und AP-17-Abnahmen bleiben verpflichtende Regressionsgates und
   werden nicht durch die neue elektrische Matrix ersetzt.

## Messbare Abnahme

AP 18 gilt erst als abgeschlossen, wenn alle folgenden Kriterien automatisiert
geprüft sind:

- Die drei versionierten Verträge stimmen untereinander sowie mit Assembler,
  VM, Debugger und öffentlichen Schaltungspins überein.
- Ein Programm schreibt gültige und ungültige Werte auf den Ausgabeport; VM
  und Logisim zeigen an jeder Flanke identische Werte und Validitätsbits, ohne
  die RAM-Zelle an der reservierten Adresse zu verändern.
- Interrupts unmittelbar vor, während und nach jeder Instruktionsfamilie
  werden erst an der nächsten Instruktionsgrenze angenommen. PC,
  Rückkehradresse, Maske und Pending-Bit stimmen taktweise mit der VM überein.
- Maskierung, eine während der Maskierung eintreffende Anforderung,
  Entmaskierung und Rückkehr werden in einem reproduzierbaren End-to-End-Trace
  geprüft.
- Reset wird in Idle, bei ausstehendem Interrupt und im Handler geprüft und
  stellt für sämtliche neuen Zustände die dokumentierten Resetwerte her.
- Eine illegale Rückkehr und ein ungültiger Vektorzugriff erzeugen die
  festgelegten Sticky-Fehler und denselben Haltgrund in VM und Logisim.
- Die elektrische Matrix deckt jeden neuen Opcode sowie Annahme, Maskierung,
  Pending-Verhalten, Rückkehr, Reset und beide Fehlerpfade ab; Metadaten
  verhindern ungetestete Vertragsfälle.
- Offline-Suite und elektrische Gates für `tinycpu-16-12` und `tinycpu-8-8`
  bleiben unverändert erfolgreich.

## Umsetzungsreihenfolge

1. Systemprofil, Maschinenformat und erweitertes Trace-Schema festlegen.
2. ~~Assembler, VM und Debugger hinter einer expliziten Systemprofilauswahl
   erweitern und Referenztests für sämtliche Prioritätsfälle ergänzen.~~
3. Die eigenständige Logisim-Schaltung mit Ausgabeport und
   Interruptsteuerung erstellen.
4. End-to-End-Fixtures und die vollständige elektrische Peripheriematrix gegen
   die VM ausführen.
5. Das neue Gate zusätzlich zu AP 12 und AP 17 in CI aufnehmen und Bedienung,
   Kompatibilitätsgrenzen sowie Nachweisartefakte dokumentieren.

Diese Reihenfolge ist die Grenze des geplanten AP 18. Die Implementierung darf
die festgelegten Verträge präzisieren, aber weder zusätzliche Geräte noch eine
Änderung bestehender Profile stillschweigend in das Paket aufnehmen.

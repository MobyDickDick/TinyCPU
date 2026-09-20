# Vorschlag: Peripherie und Integration

**Status: in Umsetzung (elektrische Systemintegration ausstehend).** Dieses Dokument trifft
die nach AP 17 noch offene Produktentscheidung. Die Richtung **Peripherie und Integration** wird als
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

Die eigenständige Datei `TinyCPU_Peripherals.circ` friert nun außerdem die
elektrische Systemgrenze ein. Ihr Top-Level `TinyCPUSystemMain` exportiert die
Interruptanforderung und sämtliche zusätzlichen Trace-Zustände als direkte
Pins. Der Offline-Prüfer gleicht Richtung und Breite jedes Pins mit dem
Systemprofil ab. Die interne Verdrahtung des Ausgabeports und der
Interruptsteuerung sowie deren elektrische Abnahme bleiben die nächsten
Teilschritte von AP 18; die neue Datei wird daher noch nicht vom elektrischen
Release-Gate als fertige System-CPU behandelt.

Der erste interne Baustein `OutputPort` ist jetzt ebenfalls Bestandteil der
Schaltung. Zwei taktsynchrone Register übernehmen Wert und Validität gemeinsam
nur bei der akzeptierten Schreibbedingung `WRITE_VALID AND WRITE_ENABLE`;
`RESET` löscht beide Zustände. Sein maschinenlesbarer
Komponentenvertrag und der Offline-Prüfer sichern Pinrichtungen, Breiten, die
beiden getrennten Zustandsregister und nun auch jeden Daten-, Freigabe-, Takt-,
Reset- und Ausgangspfad ab. Damit kann weder eine nur einseitige Freigabe noch
ein vom Wert entkoppeltes Valid-Bit unbemerkt in die elektrische Abnahme
gelangen. Der neue Baustein
`OutputMemoryPath` friert jetzt auch die Speicherpfadgrenze ein: Er dekodiert
ausschließlich Adresse `0xfff`, trennt Port- und RAM-Schreibfreigabe und beschreibt die Auswahl von Wert und Validität beim Lesen.
Der Komponentenvertrag und der Offline-Prüfer sichern dabei Adress- und
Datenbreiten, die reservierte Adresse sowie nun auch die tatsächlich
verdrahteten, getrennten Lese- und Schreibpfade ab. Der Adressvergleich sperrt
RAM-Schreibzugriffe auf `0xfff`, gibt dort ausschließlich den atomaren
Port-Schreibpfad frei und schaltet Wert und Validität gemeinsam auf den
Portzustand um; Takt und Reset erreichen den gekapselten `OutputPort` direkt.
Ein Mutationstest entfernt gezielt eine dieser Leitungen und stellt sicher,
dass der Offline-Prüfer die Verdrahtungslücke erkennt. Der Baustein
`InterruptController` friert zusätzlich die
elektrische Interruptsteuerungsgrenze ein: Seine Pins führen Flankenanforderung,
Instruktionsgrenze, Maskenbefehle, Rückkehrbefehl und nächsten PC sowie Annahme,
Sprungziel, sämtliche Interruptzustände und den Fehler einer illegalen
Rückkehr. Sechs getrennte Register besitzen Request-Pegel, Maske, Pending-Bit,
Handlerzustand und Rückkehradresse samt Validität; Vektor, Breiten und die
benannten Flanken-, Annahme- und Rückkehrpfade werden offline gegen den
Systemvertrag geprüft. Der erste funktionale Pfad tastet den externen
Anforderungspegel an jeder Taktflanke ab, setzt ihn bei Reset zurück und bildet
aus aktuellem sowie invertiertem vorherigem Pegel ausschließlich einen
Anstiegsimpuls. Komponentenvertrag und Leitungs-Mutationstest sichern diesen
Pfad direkt an den Bauteilanschlüssen. Der Anstiegsimpuls setzt nun das
taktsynchrone Pending-Register; dessen Rückkopplung hält eine während der
Maskierung eingetroffene Anforderung, und Reset löscht den Zustand. Der
Komponentenvertrag prüft Setz-, Halte-, Takt-, Reset- und Ausgangspfad direkt.
Die Annahmelogik verknüpft Pending-Zustand, aktivierte Maske,
Instruktionsgrenze und den invertierten Handlerzustand. Ihr Annahmeimpuls wird
direkt ausgegeben und löscht über einen eigenen Rückkopplungspfad das
Pending-Bit, sofern nicht gleichzeitig eine neue Anforderungsflanke eintrifft.
Der Komponentenvertrag und ein Leitungs-Mutationstest schützen sowohl die vier
Annahmebedingungen als auch Ausgabe und Löschpfad. Die Maskenlogik setzt den
taktsynchronen Zustand durch `ENABLE_REQUEST` oder eine Rückkehr, löscht ihn
durch `DISABLE_REQUEST` oder Interruptannahme und hält ihn andernfalls über
einen expliziten Rückkopplungspfad. Takt, Reset und der öffentliche
Zustandsausgang sind vertraglich geprüft; ein Mutationstest schützt den
Next-State-Pfad. Die funktionale Verdrahtung dieser Grenzen in die vollständige
CPU folgt weiterhin innerhalb von Schritt 3. Bei einer Interruptannahme übernimmt
das Rückkehradressregister inzwischen `NEXT_PC`; derselbe Annahmeimpuls setzt das
zugehörige Validitätsregister. Beide Register teilen sich Takt und Reset und
führen ihre Zustände direkt an die öffentlichen Ausgänge. Der Komponentenvertrag
und ein gezielter Leitungs-Mutationstest schützen Daten-, Annahme-, Takt-,
Reset- und Ausgangspfade. Eine zulässige Rückkehr wird nun nur aus
`RETURN_REQUEST`, aktivem Handlerzustand und gültiger Rückkehradresse gebildet.
Dieser Impuls löscht das Validitätsbit; ohne ihn hält dessen expliziter
Rückkopplungspfad den Zustand, während eine neue Interruptannahme weiterhin
Vorrang beim Setzen hat. Der Komponentenvertrag und ein Leitungs-Mutationstest
schützen die drei Bedingungen sowie Lösch-, Halte- und Setzpfad. Der
Handlerzustand wird bei einer Interruptannahme gesetzt, bis zu einer gültigen
Rückkehr gehalten und durch genau diesen Rückkehrimpuls gelöscht. Dabei wurden
die zuvor nur strukturell beanspruchten Registeranschlüsse berichtigt:
`NEXT_PC` speist das Rückkehradressregister und der Validitäts-Next-State das
zugehörige Validitätsregister; beide Zustände besitzen nun ihre eigenen
Takt- und Resetpfade. Komponentenvertrag und Leitungs-Mutationstest schützen
auch den Handler-Next-State-Pfad. Der Zielmultiplexer liefert im normalen
Interruptpfad den festen Vektor und schaltet ausschließlich beim gültigen
Rückkehrimpuls auf die gespeicherte Rückkehradresse um. Daten-, Auswahl- und
Ausgangspfad sind vertraglich geprüft und durch einen gezielten
Leitungs-Mutationstest geschützt. Die neuen, lokal benannten Tunnel sind eine
dokumentierte Ausnahme von der sonst bevorzugten Direktverdrahtung: Direkte Rückleitungen würden im
bereits belegten Registerkorridor bestehende Zustandsnetze kreuzen. Bei einem
späteren Redraw ist diese Ausnahme erneut zu prüfen.

Der Offline-Prüfer bleibt auch nach einem regulären Speichern der Zeichnung in
Logisim stabil: Bauteile, deren Beschriftungen Logisim nicht sichtbar rendert
und beim Speichern entfernt, werden über Typ, Breite, Vertragswert und ihre
direkten Portverbindungen erkannt. Die Mutationstests prüfen weiterhin echte
Register- und Multiplexerpfade und verlangen keine unsichtbaren Labels als
Ersatz für elektrische Konnektivität.

Die vollständige elektrische Fallliste ist inzwischen vor der
Systemintegration als `tinycpu-system-electrical-matrix-v1.json` eingefroren.
Sie verknüpft jedes Szenario mit dem System-, Maschinenformat- und
Trace-Vertrag, enthält deterministische externe Ereignisse pro Taktflanke und
deckt alle drei neuen Opcodes sowie Ausgabevalidität, Maskierung, Annahme,
Rückkehr, Reset und beide Fehlerpfade ab. Der Offline-Verifier assembliert die
Programme und lehnt fehlende oder unbekannte Abdeckung ab. Diese Fallliste ist
noch **kein** elektrischer Nachweis: Ihre Ausführung gegen die VM beginnt erst,
wenn die Bausteine funktional in die vollständige CPU eingefügt sind.

Als erster Integrationsschritt enthält `TinyCPUSystemMain` die beiden
Bausteingrenzen jetzt genau einmal. Die Zustandsausgänge des Ausgabeports und
der Interruptsteuerung sind mit sichtbaren Leitungen direkt bis zu allen sieben
öffentlichen Trace-Pins geführt. Der Offline-Prüfer verfolgt dabei die echten
Ausgänge der generierten Bausteinsymbole; ein Entfernen einer Leitung lässt die
Abnahme gezielt fehlschlagen. Die nachfolgende Kontrolle der vom
Schaltungsautor umgezeichneten Fassung hat die funktionalen Leitungen der drei
Bausteine bestätigt und die zugehörigen Top-Level-Koordinaten in den
Regressionen nachgeführt. Die kanonische Leitungsliste des besonders
rückkopplungsreichen `InterruptController` ist zusätzlich im
Komponentenvertrag gehasht; jede entfernte oder hinzugefügte Leitung bricht
damit die Offline-Abnahme ab, ohne die neue Anordnung zurückzuzeichnen.

Als nächster Integrationsschritt sind nun `CLK`, `RESET` und
`INTERRUPT_REQUEST` vom öffentlichen Systemeingang direkt zu den jeweils
betroffenen Bausteinen geführt. Der Offline-Prüfer und ein Mutationstest
schützen alle fünf Endanschlüsse. Die CPU-Datenpfade sowie die Befehls- und
PC-Steuerpfade sind auf dem Top-Level weiterhin nicht angeschlossen. Dieser
Schritt behauptet daher weder einen ausführbaren Systemkern noch einen
elektrischen Matrixnachweis; als nächstes folgt die Einfügung dieser
CPU-seitigen Daten-, Befehls- und PC-Steuerpfade.

Vor dieser Einfügung ist deren vollständige elektrische Schnittstelle jetzt
als `CPUIntegrationBoundary` festgeschrieben. Sie trennt RAM-Lesedaten und
-Gültigkeit von der durch `OutputMemoryPath` ausgewählten Leseseite, führt die
Schreibadresse samt Wert, Gültigkeit und Freigaben und benennt sämtliche drei
neuen Befehlsimpulse sowie Instruktionsgrenze, Folge-PC, Interruptannahme,
Interruptziel und illegale Rückkehr. Der Systemvertrag und Offline-Prüfer
gleichen für jeden Pin Richtung und Breite ab; ein Mutationstest schützt die
Grenze. Sie ist bewusst noch nicht auf dem Top-Level instanziiert und enthält
noch keinen CPU-Kern. Als nächster Schritt folgt daher die Implementierung
hinter dieser Grenze und erst danach ihre direkte Verdrahtung mit
`OutputMemoryPath` und `InterruptController`.

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

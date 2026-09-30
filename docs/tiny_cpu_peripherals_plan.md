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
`OutputMemoryPath` und `InterruptController`. Als erster funktionaler Pfad
hinter dieser Grenze werden RAM-Lesewert und zugehörige Gültigkeit nun direkt
und gemeinsam an die CPU-seitige Leseauswahl weitergereicht. Der
Offline-Prüfer und ein Mutationstest sichern beide Leitungen; Adress-, Schreib-,
Befehls- und PC-Steuerpfade bleiben die folgenden Integrationsschritte. Nach
der manuellen Neuanordnung der Grenzpins verfolgt die Regression diese beiden
Pfade anhand der benannten Anschlüsse statt anhand ihrer Zeichenkoordinaten.
Damit bleibt die elektrische Aussage erhalten, ohne die vom Schaltungsautor
gewählte Darstellung zurückzuzeichnen.
Der anschließende Integrationsschritt reicht nun auch die 12-Bit-Adresse vom
explizit benannten, vorläufigen Kernanschluss `CORE_ADDRESS` direkt bis zum
Ausgang `ADDRESS` der Grenze weiter. Vertrag, Offline-Prüfer und derselbe
Leitungs-Mutationstest sichern den Pfad anhand der Pinbezeichnungen ab. Damit
ist der Adresspfad vorbereitet, ohne bereits einen nicht vorhandenen
ausführbaren CPU-Kern zu behaupten; Schreib-, Befehls- und PC-Steuerpfade
bleiben offen. Als nächster abgegrenzter Pfad reichen nun auch Schreibwert,
Schreibgültigkeit und Schreibfreigabe von den drei ausdrücklich benannten,
vorläufigen Kernanschlüssen direkt zu den entsprechenden Ausgängen der Grenze.
Vertrag, Offline-Prüfer und Leitungs-Mutationstest sichern die drei Signale
gemeinsam anhand ihrer Pinbezeichnungen. Damit ist der CPU-seitige Schreibpfad
bis zur Speichergrenze vollständig vorbereitet; Befehls- und PC-Steuerpfade
sowie die Top-Level-Verdrahtung bleiben offen. Der folgende abgegrenzte Schritt
führt nun die Instruktionsgrenze und die drei Befehlsimpulse für Aktivierung,
Deaktivierung und Rückkehr von ausdrücklich benannten, vorläufigen
Kernanschlüssen direkt zu den Interruptausgängen der Grenze. Vertrag,
Offline-Prüfer und Leitungs-Mutationstest sichern alle vier Signale anhand der
Pinbezeichnungen. Damit bleibt innerhalb der CPU-Grenze nur noch der
PC-Steuerpfad offen; die Top-Level-Verdrahtung ist weiterhin nicht eingefügt.
Dieser letzte interne Pfad führt nun den 12-Bit-Folge-PC vom benannten,
vorläufigen Kernanschluss `CORE_NEXT_PC` direkt zum Ausgang `NEXT_PC` der
Interruptsteuerung. Vertrag, Offline-Prüfer und Leitungs-Mutationstest sichern
auch diese Verbindung anhand der Pinbezeichnungen. Damit ist die interne
CPU-Grenze für Daten-, Befehls- und PC-Steuerpfade vorbereitet. Der erste
Top-Level-Schritt ist nun ebenfalls erfolgt: `TinyCPUSystemMain` enthält genau
eine Instanz der `CPUIntegrationBoundary`; ein gezielter Mutationstest schützt
diese Systemstruktur. Die vom Schaltungsautor angepasste, geknickte
RAM-Lesewertleitung innerhalb der Grenze wird dabei anhand ihrer tatsächlichen
Netzkonnektivität statt einer überholten direkten Linie geprüft. Als nächster
Integrationsschritt ist die platzierte Grenze nun direkt mit
`OutputMemoryPath` und `InterruptController` verdrahtet. Lese-, Schreib- und
Adresspfad sowie Befehls-, Folge-PC-, Annahme-, Ziel- und Fehlerpfad werden an
den tatsächlichen Ports der generierten Symbole geprüft; ein Mutationstest
entfernt dazu einzeln jeden der 15 Endanschlüsse. Ein ausführbarer elektrischer
Systemkern wird damit noch nicht behauptet: Als nächstes folgt die Anbindung
der vorläufigen Kernanschlüsse an die vollständige CPU und danach die
Ausführung der Systemmatrix.

Die vollständige, unveränderte `TinyCPUMain`-CPU ist dafür nun als externe
Projektbibliothek genau einmal innerhalb der `CPUIntegrationBoundary`
platziert. Der Komponentenvertrag benennt sowohl die Quelldatei als auch den
Schaltungsnamen; der Offline-Prüfer und ein Mutationstest verhindern, dass die
Instanz oder ihre eindeutige Bibliothekszuordnung unbemerkt verloren geht.
Damit ist die bisher ausschließlich aus vorläufigen Anschlüssen bestehende
Grenze erstmals an den abgenommenen Kern gebunden, ohne dessen Schaltbild zu
kopieren oder umzuzeichnen. Takt und Reset sind nun von den Eingängen der
Integrationsgrenze direkt mit den beiden Eingängen des vollständigen Kerns
verbunden. Der Komponentenvertrag, der Offline-Prüfer und ein Mutationstest
schützen beide Pfade bis an die tatsächlichen Kernanschlüsse. Der vom Kern für
adressierte Ausgaben bereitgestellte Speicherwert und sein Gültigkeitsbit
erreichen nun direkt die beiden Leseausgänge des Adapters. Der
Komponentenvertrag und ein Mutationstest schützen beide Leitungen bis zu den
tatsächlichen Ausgängen des generierten Kernsymbols. Als additive
Kernschnittstelle sind nun `EXTERNAL_MEMORY_VALUE`, `EXTERNAL_MEMORY_VALID`
und `USE_EXTERNAL_MEMORY` ergänzt. Die Systemgrenze führt ausgewählten Wert
und Gültigkeit direkt an diese neuen Eingänge und aktiviert die Schnittstelle;
Komponentenvertrag, Offline-Prüfer und Mutationstest schützen beide
Datenleitungen bis zum Kern. Im vollständigen Kern wählen nun zwei getrennte,
gleichzeitig von `USE_EXTERNAL_MEMORY` gesteuerte Multiplexer zwischen diesen
Eingängen und dem bisherigen RAM-Wert samt Gültigkeit. Die ausgewählten
Signale speisen alle bisherigen Speicherleseverbraucher; ein Leitungs-
Mutationstest schützt interne und externe Eingänge, Auswahl und Ausgänge. Ohne
Aktivierung bleibt der bisherige RAM-Pfad erhalten. Als erster Teil der
übrigen Kernanschlüsse stellt `TinyCPUMain` nun auch genau die drei Signale
bereit, die seinen bisherigen RAM-Schreibpfad treiben: Schreibwert,
Gültigkeit und Freigabe. Die Ausgänge hängen direkt an denselben Netzen wie die
RAM-Eingänge, sodass die spätere Speicherweiche Wert und Gültigkeit nicht
voneinander trennen und keine zweite Schreibdekodierung einführen kann. Der
Komponentenvertrag prüft Richtung und Breite; ein Leitungs-Mutationstest
schützt jeden der drei Pfade bis zum öffentlichen Kernanschluss. Ihre
Verbindung mit der `CPUIntegrationBoundary` ist nun ebenfalls abgeschlossen:
Die drei vorläufigen Eingabepins wurden entfernt, und Schreibwert, Gültigkeit
und Freigabe laufen direkt von den tatsächlichen Kernausgängen zu den
Ausgängen der Integrationsgrenze. Der Offline-Prüfer und ein Mutationstest
verfolgen diese Pfade anhand der benannten Kern- und Adapterports, sodass eine
manuelle Verschiebung der Pins nicht durch alte Canvas-Koordinaten
zurückgespielt wird. Als nächster begrenzter Integrationsschritt sind nun auch
die Befehlswege eingefügt. Ein eigener 6-Bit-Decoder des vollständigen Kerns
erzeugt aus den Systemopcodes 56, 57 und 58 die Impulse für Aktivierung,
Deaktivierung und Rückkehr; die bei jeder Kerninstruktion aktive
Instruktionsgrenze wird getrennt herausgeführt. Die vier vorläufigen
Befehlseingänge der `CPUIntegrationBoundary` wurden entfernt und durch direkte
Leitungen von den tatsächlichen Kernausgängen ersetzt. Vertrag, Offline-Prüfer
und Mutationstest sichern Opcode-Zuführung, Decoder-Ausgänge, öffentliche
Kernpins und Adapterpfade gemeinsam. Als nächster abgegrenzter Schritt bleibt
damit der PC-Steuerpfad vom vollständigen Kern zur Interruptsteuerung. Nach der
manuellen Neuanordnung wurde zunächst der Prüfer an die tatsächlich in
`FetchDecodeControls` liegenden Befehlsdekodierungen und die verschobenen
Speicherselektoren angepasst; die entfernte, doppelte Top-Level-Dekodierung
wird ausdrücklich nicht wiederhergestellt. Der vollständige Kern exportiert
nun außerdem seinen bereits vorhandenen Folge-PC als 12-Bit-Ausgang
`NEXT_PC`. `CPUIntegrationBoundary` führt diesen tatsächlichen Kernausgang
anstelle des bisherigen vorläufigen Eingangs direkt zur Interruptsteuerung.
Vertrag, Offline-Prüfer und zwei gezielte Leitungs-Mutationstests schützen den
Kern- und Adapterpfad. Die Eingänge für Interruptannahme und Interruptziel steuern den PC des Kerns
nun prioritätsgerecht: Ein angenommener Interrupt wählt `TARGET_PC` über einen
zusätzlichen 12-Bit-Multiplexer, während `ILL_RET` den vorhandenen
Sticky-Fehlerpfad für illegale Operationen speist. Dieselben drei
Rückkopplungen sind in Integrationsgrenze, Kern und eigenständigem
`FetchDecode`-Diagnoseblatt durchgehend verdrahtet und werden vom Offline-Prüfer
sowie den Leitungs-Mutationstests geschützt.
Der anschließende, ausschließlich topologische Vergleich bestätigt nun auch
den eingebetteten Opcode-Pfad: Das vollständige 22-Bit-Instruktionswort läuft
vom benannten `FetchDecode.OPCODE`-Ausgang zum Splitter, dessen Zweig für Bits
16 bis 21 den benannten `FetchDecodeControls.OPCODE`-Eingang speist. Der Prüfer
leitet sämtliche Anschlüsse aus Bausteindefinition, Instanz und
Netzkonnektivität ab; weder die aktuelle Position der drei Bausteine noch ein
früherer Leitungsverlauf ist Bestandteil des Vertrags. Ein gezielter
Mutationstest trennt den Decoder-Eingang und läuft damit auch im ausgelagerten
GitHub-Offline-Gate.

Der zuvor offene Eingang `RAM_WRITE_ENABLE` ist nun über einen vom bestehenden
`USE_EXTERNAL_MEMORY` gesteuerten Selektor mit dem Schreibfreigabeeingang der
privaten `Memory`-FBox verbunden. Ohne externen Speichermodus bleibt der
bisherige interne Schreibpfad ausgewählt.

Eine erneute Top-Level-Kontrolle folgt jetzt nicht mehr den absoluten
Zeichenkoordinaten der drei generierten Bausteinboxen. Der Offline-Prüfer
ermittelt deren Anschlüsse aus den benannten Pins der jeweiligen
Schaltungsdefinition, ihrer Richtung und der von Logisim erzeugten
Anschlussreihenfolge und verfolgt anschließend ausschließlich die
Netzkonnektivität. Ein Regressionstest verschiebt das gesamte Top-Level samt
Leitungen und Pins und verlangt unverändert dieselbe elektrische Aussage. Bei
dieser Kontrolle wurden die nach einer manuellen Neuanordnung vertauschten
CPU-Ausgänge wieder ihren semantischen Zielen zugeordnet: Adresse,
Schreibwert, Schreibgültigkeit, Befehlsimpulse und Folge-PC erreichen nun die
jeweils gleichnamigen Speicher- beziehungsweise Interruptanschlüsse. Der
Logisim-Tabellenprüfer bestätigt für das System-Top-Level definierte Ausgänge
ohne Breitenfehler. Die eingefrorene Systemmatrix ist als fokussierter
Diagnoselauf ausführbar: Für jeden Fall wird das Systemprogramm samt
Vektorhandler in eine temporäre Kernkopie geladen, aus denselben externen
Flankenereignissen ein VM-Referenzlauf erzeugt und als sequenzieller
Logisim-Testvektor gegen alle sieben öffentlichen Systemzustände geprüft.
Logisim 4.1.0 initialisiert über seinen regulären Programmeinstieg selbst für
diesen nichtinteraktiven Aufruf Swing. Das Gate ruft den öffentlichen
Testvektor-Evaluator deshalb über den kleinen Java-Quellstarter
`scripts/LogisimHeadlessVector.java` direkt auf. Der elektrische Lauf benötigt
damit weder `DISPLAY` noch `xvfb-run`; Simulator und Auswertelogik stammen
weiterhin aus dem gepinnten Logisim-JAR. Als nächster Schritt bleibt die
Auswertung des ersten vollständigen elektrischen Laufs und die kleinste
Reparatur eines dabei nachgewiesenen Signalfehlers.

Für diesen Diagnosezyklus kann die Systemmatrix nach einem fehlgeschlagenen
Gesamtlauf gezielt wiederholt werden, ohne zuvor erneut die 61 unveränderten
Kernfälle auszuführen:

```bash
PYTHONPATH=src python3 src/tiny_cpu_logisim.py \
  --profile tinycpu-16-12 --system tinycpu-peripherals-16-12-v1 \
  --system-only --trace-output /tmp/unused-core.tsv \
  --matrix-output artifacts/tinycpu-system-diagnostic
```

`--system-only` ist ausdrücklich ein fokussierter Diagnoseaufruf. Solange noch
ein dokumentierter elektrischer Systemunterschied besteht, bleibt die Matrix
gemäß der Umsetzungsreihenfolge außerhalb von `scripts/test-logisim.sh`:
Schritt 5 nimmt das neue Gate erst **nach** der grünen End-to-End-Matrix auf.
Das bestehende verpflichtende Kern-Gate wird damit nicht durch eine noch nicht
abgenommene optionale Systemvariante rot geschaltet.

Der damit erstmals ohne grafische Umgebung ausgeführte Lauf stoppt wie von
der Diagnose-Stopregel verlangt im ersten Fall `output-valid-write`. Die
Vektoren 1 bis 3 stimmen überein; ab Vektor 4 bleibt
`OUTPUT_PORT_VALUE` bei `0x0000` statt `0x0017` und
`OUTPUT_PORT_VALID` bei `0` statt `1`. Die übrigen fünf Fälle wurden nach
diesem ersten Unterschied nicht ausgeführt. Als nächstes wird deshalb nur die
Kette aus CPU-Schreibwert, -gültigkeit und -freigabe bis zu den beiden
Ausgabeportregistern untersucht; aus diesem Befund wird noch keine Änderung
an Interrupt- oder PC-Pfaden abgeleitet.

Der fokussierte Lauf bewahrt dafür nun pro Fall nicht nur die zusammengefasste
Logisim-Ausgabe auf, sondern auch den tatsächlich geprüften Vektor, die mit
dem Fall-ROM versehene `TinyCPU.circ` und die zugehörige
`TinyCPU_Peripherals.circ`. Diese vier Dateien liegen gemeinsam im nach der
Fall-ID benannten Artefaktverzeichnis. Damit bleibt gerade der erste
Fehlschlag nach dem Abbruch unverändert reproduzierbar und kann mit internen
Messpins untersucht werden, ohne das ROM oder den erwarteten Flankenverlauf
nachträglich rekonstruieren zu müssen. Ein Regressionstest erzwingt dieses
Diagnosepaket auch bei einem fehlgeschlagenen Simulatorprozess. Die
elektrische Abweichung selbst bleibt unverändert bestehen; das Aufbewahren
der Eingaben wird nicht als Reparatur oder elektrische Abnahme gewertet.

Der folgende begrenzte Diagnoseschritt macht den bereits beobachteten ersten
Unterschied zusätzlich maschinenlesbar. Bei einem fehlgeschlagenen Fall legt
der Matrixlauf neben der unveränderten Simulatorausgabe eine
`diagnostic.json` ab. Sie nennt die Fall-ID, den ersten fehlerhaften Vektor und
alle dort von Logisim gemeldeten Signalwerte. Für `output-valid-write` sind
das weiterhin Vektor 4 sowie `OUTPUT_PORT_VALUE` und `OUTPUT_PORT_VALID`;
spätere Vektoren werden dadurch ausdrücklich nicht als frühere Ursache
fehlinterpretiert. Die Datei ist ein Diagnoseindex, kein Ersatz für den
elektrischen Bericht und noch keine Reparatur der Schreibsignalkette.

Die erste interne Messung grenzt diese Schreibsignalkette jetzt weiter ein.
Temporäre, ausschließlich im gesicherten Diagnosepaket ergänzte Top-Level-
Messpins zeigen an Vektor 4 `WRITE_VALUE=0x0017`, aber
`WRITE_VALID=0`, `WRITE_ENABLE=0` und `ADDRESS=0x001`;
`INTERRUPT_ACCEPT` bleibt dabei erwartungsgemäß null. Damit sind Ausgabeport,
Interruptannahme und der transportierte Schreibwert nicht der erste
abweichende Übergang. Der Fehler liegt vor der Speichergrenze in der
CPU-seitigen Erzeugung von Adresse, Gültigkeit und Freigabe. Die Messpins
wurden nicht in die veröffentlichte Systemgrenze übernommen und an der
Schaltung wurde gemäß Stop-Regel noch kein weiterer Pfad geändert. Als
nächstes werden diese drei Signale innerhalb des Kerns bis zu Decoder und
effektiver Adresse zurückverfolgt.

Die damalige Rückverfolgung auf Ausgangsstand `c299d74` war falsch: Beim
ostwärts gerichteten Splitter führt der obere Ausgang bei `(700,490)` den im
Attributsatz der Verzweigung `0` zugeordneten 12-Bit-Anteil (Bits 0 bis 11).
Der untere Ausgang bei `(700,500)` führt dagegen ausschließlich die vier Bits
12 bis 15. Die vermeintliche Reparatur verband daher einen 4-Bit-Ausgang mit
dem 12-Bit-Pin `ADDRESS` und erzeugte den in Logisim sichtbaren Breitenfehler.
Die Leitung liegt wieder auf dem 12-Bit-Ausgang. Verifier und Mutationstest
prüfen jetzt sowohl die Bitzuordnung als auch diesen tatsächlichen Anschluss.

Der fokussierte elektrische Lauf erreicht nach der Korrektur weiterhin den
ersten Fall `output-valid-write`, beendet ihn aber noch nicht erfolgreich. Der
Breitenfehler war ein durch die fehlerhafte Reparatur hinzugefügter Defekt und
nicht die Erklärung für den schon zuvor ausbleibenden Portschreibvorgang.
Gemäß der Stop-Regel werden Decoder, Gültigkeits- und Freigabepfad getrennt
untersucht.

Die anschließende topologische Kontrolle des manuell neu angeordneten Stands
hat verlorene elektrische Attribute gefunden, ohne Bauteile oder Leitungswege
nach alten Koordinaten zurückzuverschieben. `INSTRUCTION_BOUNDARY_ASSERTED` und
`USE_EXTERNAL_MEMORY` treiben wieder den Vertragswert `1`; die vorhandenen
PC- und RAM-Schreibselektoren tragen wieder ihre semantischen Bezeichner. Der
Offline-Verifier prüft am 16-auf-12-Bit-Adapter Bitzuordnung und den dazu
passenden Ausgang gemeinsam.

Der fokussierte elektrische Lauf bleibt danach reproduzierbar im ersten Fall
`output-valid-write` an Vektor 4 stehen. Damit ist die topologische Kontrolle
abgeschlossen, aber noch keine elektrische Freigabe erreicht; als nächstes
werden ausschließlich `EXTERNAL_WRITE_VALID` und `EXTERNAL_WRITE_ENABLE` am
Kernausgang mit ihren RAM-seitigen Ursprungsnetzen verglichen.

Diese Anschlusskontrolle ist nun erfolgt. Sie folgt den vollständigen Netzen
und den benannten Bauteilports und bewertet weder die optische Nähe noch alte
Canvas-Koordinaten als Verbindung. Dabei wurden nach dem erneuten manuellen
Speichern drei verlorene Bauteilattribute (`INSTRUCTION_BOUNDARY_ASSERTED`,
`INTERRUPT_PC_OVERRIDE` und `RAM_WRITE_ENABLE_SELECT`), der Vertragswert von
`USE_EXTERNAL_MEMORY` gefunden. Die zunächst zusätzlich behauptete offene
12-Bit-Adressleitung war eine Fehlinterpretation der Splitterausgänge und ist
wie oben beschrieben korrigiert. Kein Bauteil wurde verschoben.

`EXTERNAL_WRITE_VALID` und `EXTERNAL_WRITE_ENABLE` sind danach topologisch mit
ihren RAM-seitigen Ursprungsnetzen verbunden. Der fokussierte elektrische Lauf
liefert trotzdem an Vektor 4 weiterhin für beide Signale logisch `0`, während
der Schreibwert bereits `0x0017` erreicht. Der erste noch offene funktionale
Unterschied liegt damit nicht an der CPU-Integrationsgrenze, sondern vor den
beiden Exporten in der Erzeugung von Gültigkeit und Schreibanforderung. Als
nächster eng begrenzter Diagnoseschritt werden deren benannte Eingänge am
`MEMORY_WRITE_REQUEST`-Gatter und am Gültigkeitspfad verfolgt; andere Daten-,
Interrupt- oder PC-Pfade bleiben dabei unverändert.

Diese begrenzte Kontrolle hat zwei falsche Quellen am dreifachen
`MEMORY_WRITE_REQUEST`-Gatter nachgewiesen: Statt `STORE_ADR` und
`STORE_ADR_REG` waren `SET_DIV0` und `SET_ADDR` angeschlossen; nur
`STORE_REG_OFF` erreichte bereits den richtigen Eingang. Die beiden offenen
Store-Ausgänge sind nun über getrennte sichtbare Leitungen angeschlossen. Ein
semantischer Strukturtest verfolgt alle drei Decoder-Ausgänge bis zu jeweils
einem eigenen Gate-Eingang und ein Mutationstest entfernt gezielt den ersten
Pfad. Der Gültigkeitseingang des RAM und der Export
`EXTERNAL_WRITE_VALID` liegen dagegen bereits gemeinsam und ohne Unterbrechung
auf `Datapath.ACC_VALID_OUT`.

Der anschließende fokussierte elektrische Lauf bleibt im Fall
`output-valid-write` an Vektor 4 stehen: Ausgabeportwert und -gültigkeit sind
weiterhin null. Die falschen Gate-Quellen waren damit ein realer
Topologiefehler, aber noch nicht der letzte funktionale Unterschied. Als
nächster Diagnoseschritt werden die drei korrigierten Store-Ausgänge während
dieses Vektors direkt gemessen; erst danach darf entweder der Decoder oder der
nachfolgende Schreibpfad geändert werden.

Diese direkte Messung ist auf Ausgangs-Commit `d00451a` erfolgt. Nach der
topologischen Wiederherstellung der beim Speichern verlorenen semantischen
Attribute wurde der fokussierte Lauf mit

```bash
LOGISIM_JAR=.venv/Include/logisim-evolution-4.1.0-all.jar \
PYTHONPATH=src python3 src/tiny_cpu_logisim.py \
  --profile tinycpu-16-12 --system tinycpu-peripherals-16-12-v1 \
  --system-only --trace-output /tmp/unused-core.tsv \
  --matrix-output artifacts/tinycpu-system-diagnostic
```

reproduziert. Temporäre Messpins am vorhandenen
`FetchDecodeControls`-Symbol zeigen in der Schreibphase für `STORE_ADR`,
`STORE_ADR_REG` und `STORE_REG_OFF` jeweils `0`; für den ausgeführten
`STORE_ADDRESS`-Befehl müsste ausschließlich `STORE_ADR` den Wert `1` liefern.
Damit sind die drei Leitungen vom Symbol bis zum `MEMORY_WRITE_REQUEST`-Gatter
nicht der erste abweichende Pfad. Der erste elektrische Unterschied liegt
spätestens am benannten Decoder-Ausgang `STORE_ADR`; die temporären Messpins
wurden nicht in die Schaltung übernommen. Als nächstes werden nur der
`OPCODE`-Eingang und der `STORE_ADR`-Ausgang von `FetchDecodeControls`
elektrisch gegeneinander geprüft. Wegen der geschützten handgezeichneten
Darstellung wird vor diesem Nachweis weder der Decoder umgezeichnet noch eine
Verbindung anhand von Canvas-Koordinaten bewertet.

Dieser Vergleich ist auf Ausgangs-Commit `b187b1c` erfolgt. Der vorhandene
elektrische Decodertest wurde zunächst an die inzwischen veröffentlichte
Schnittstelle angepasst: Der Ausgang des `NOT`-Befehls heißt dort `INVERT`,
und die Systemopcodes 56 bis 58 besitzen eigene, gültige Ausgänge statt
`INVALID_OPERAND` zu setzen. Anschließend hat

```bash
LOGISIM_JAR=.venv/Include/logisim-evolution-4.1.0-all.jar \
  python3 scripts/test-logisim-decode.py
```

alle 64 möglichen Werte direkt an den sechs `OPCODE`-Eingangsbits elektrisch
angelegt und sämtliche öffentlichen Ausgänge verglichen. Der Lauf besteht;
insbesondere setzt `0x29` ausschließlich den erwarteten Ausgang `STORE_ADR`.
Damit sind Decoderzeile und Ausgangsleitung innerhalb der geschützten
`FetchDecodeControls`-Schaltung elektrisch belegt und werden nicht verändert.
Zusammen mit der zuvor am eingebetteten Symbol gemessenen Null liegt der erste
Unterschied nun vor dem Decoder: Als nächstes wird während Vektor 4 der am
eingebetteten `OPCODE`-Eingang ankommende Wert mit dem Opcode-Ausgang von
`FetchDecode` verglichen. Andere Decoder-, Schreib-, Interrupt- und PC-Pfade
bleiben bis zu diesem Nachweis unverändert.


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

Der angekündigte eingebettete Vergleich ist auf Ausgangs-Commit `7eae3b0`
erfolgt. Ein ausschließlich in `/tmp` erzeugtes Diagnoseprojekt ergänzte am
bestehenden Opcode-Netz und am benannten `STORE_ADR`-Ausgang passive
Messpins; weder `TinyCPU.circ` noch die geschützte Darstellung von
`FetchDecodeControls` wurden verändert. Das ROM enthielt unverändert den
ersten Systemfall mit `LOAD_CONST(23)`, `STORE_ADDRESS(4095)`,
`LOAD_ADDRESS(4095)` und `HALT()`.

Die Messung korrigiert zugleich die bisherige zeitliche Zuordnung des
fehlgeschlagenen Vektors. Nach der ersten steigenden Flanke (Vektor 2) und in
der anschließenden Low-Phase (Vektor 3) führt der eingebettete Opcode-Pfad
`0x29`; `STORE_ADR` und `EXTERNAL_WRITE_ENABLE` sind jeweils `1`. An der
zweiten steigenden Flanke soll der Ausgabeport genau diese Anforderung
übernehmen. Nach dem Abklingen derselben Flanke (Vektor 4) hat der PC jedoch
bereits weitergeschaltet: Der kombinatorische Opcode-Pfad zeigt dann korrekt
`0x24`, und `STORE_ADR` sowie `EXTERNAL_WRITE_ENABLE` sind wieder `0`. Die
frühere Erwartung, am Post-Edge-Vektor 4 noch den Store-Decoderwert zu sehen,
war daher falsch; sie begründet keine Änderung am Decoder.

Der unveränderte fokussierte Systemlauf scheitert weiterhin an Vektor 4 mit
`OUTPUT_PORT_VALUE=0x0000` und `OUTPUT_PORT_VALID=0`. Der erste offene
Unterschied liegt nun hinter dem nachgewiesen korrekten Store-Decode und seiner
CPU-internen Schreibfreigabe. Als nächster enger Diagnoseschritt werden
`WRITE_ENABLE`, `WRITE_VALID` und `CLK` unmittelbar vor der zweiten steigenden
Flanke an der `CPUIntegrationBoundary` und am `OutputPort` verglichen. Erst ein
dort benannter erster Unterschied darf eine Schaltungsänderung auslösen.

Dieser Grenzvergleich ist auf Ausgangs-Commit `f22cc1f` erfolgt. Die
unveränderte erste Systemfixture wurde in einer Kopie unter
`/tmp/ap18-boundary/` um drei passive Ausgabepins erweitert. Sie beobachten
die vollständigen Netze `WRITE_ENABLE`, `WRITE_VALID` und `CLK`; die
eingecheckten Schaltungen wurden nicht verändert. Die Messpunkte liegen am
Ausgang der `CPUIntegrationBoundary`. Da die Top-Level-Leitungen diese Punkte
direkt mit den gleichnamigen Eingängen von `OutputMemoryPath` und den Takt
zusätzlich mit dessen `CLK`-Eingang verbinden, messen sie zugleich die
ankommenden Portsignale. Der eigenständige historische Teilkreis `OutputPort`
ist auf dem Systemblatt nicht instanziiert; die aktiven Portregister liegen in
`OutputMemoryPath`.

In Vektor 2, unmittelbar nach der ersten steigenden Flanke, und in der
folgenden Low-Phase (Vektor 3) ist `WRITE_ENABLE=1`. `CLK` entspricht in allen
acht Vektoren exakt dem angelegten Systemtakt. `WRITE_VALID` bleibt dagegen in
allen Vektoren `0`, also auch unmittelbar vor der zweiten steigenden Flanke,
an der die Portregister den Wert `0x0017` übernehmen sollten. Das
`OUTPUT_WRITE_GATE` kann seine drei Bedingungen aus Adressvergleich,
Schreibfreigabe und Schreibgültigkeit deshalb nicht gleichzeitig erfüllen.

Der erste elektrische Unterschied liegt damit bereits am
`WRITE_VALID`-Ausgang der `CPUIntegrationBoundary`, nicht in deren
Top-Level-Leitung, am Takt oder in den Portregistern. Gemäß Stop-Regel wurde
keine Schaltung geändert. Als nächster enger Diagnoseschritt wird nur der
CPU-interne Gültigkeitspfad von `Datapath.ACC_VALID_OUT` bis zum
`EXTERNAL_WRITE_VALID`-Pin verglichen; alle Decoder-, Freigabe-, Takt- und
Portregisterpfade bleiben bis zu diesem Nachweis unverändert.

Dieser interne Vergleich ist auf Ausgangs-Commit `5b9b3cd` erfolgt. Eine nur
unter `/tmp/ap18-internal/` instrumentierte Kopie führt
`Datapath.ACC_VALID_OUT` über einen zusätzlichen passiven Ausgang durch die
vorhandene CPU-Integrationsgrenze bis in den unveränderten ersten
Systemvektorfall. Der reguläre Export `EXTERNAL_WRITE_VALID` und der neue
Messausgang sind dort in allen acht Vektoren gleichzeitig `0`. Damit liegt
zwischen Akkumulator-Gültigkeitsregister und CPU-Export kein elektrischer
Unterschied vor; insbesondere in den Vektoren 2 und 3 reicht der Export den
tatsächlichen Zustand des Registers unverändert weiter.

Ein ergänzender Lauf derselben vier Befehle direkt auf `TinyCPUMain` trennt
den Fehler weiter ein: Dort wechselt `ACC_VALID_OUT` nach `LOAD_CONST(23)` auf
`1`, bleibt während `STORE_ADDRESS(4095)` gültig und fällt erst mit dem
nachfolgenden `LOAD_ADDRESS(4095)` erwartungsgemäß auf die noch ungültige
Speicherzelle zurück. Der Gültigkeitsspeicher und sein Ausgang funktionieren
also im eigenständigen Kernlauf. Im eingebetteten Systemlauf übernimmt der
Akkumulator zwar den Wert `0x0017`, sein Gültigkeitsregister bleibt jedoch
`0`.

Gemäß Stop-Regel wurde keine eingecheckte Schaltung verändert. Der erste noch
offene funktionale Unterschied liegt nun vor `Datapath.ACC_VALID_OUT`. Als
nächster enger Diagnoseschritt werden deshalb ausschließlich `ACC_LOAD`,
`VALID_IN` und `CLK` am `Datapath` unmittelbar vor und nach der ersten
steigenden Flanke im eingebetteten System mit dem eigenständigen Kernlauf
verglichen. Decoder-, Export-, Speicher-, Port- und Interruptpfade bleiben bis
zu diesem Nachweis unverändert.

Dieser Vergleich ist auf Ausgangs-Commit `ba31377` erfolgt. Eine ausschließlich
unter `/tmp/ap18-datapath-inputs/` instrumentierte Projektkopie führt die drei
Signale an den vorhandenen Anschlüssen des `Datapath` als passive Messausgänge
heraus. Der Lauf verwendet weiterhin den unveränderten Fall
`output-valid-write`; als Kontrolle dient dieselbe Befehlsfolge im direkt
ausgeführten `TinyCPUMain`. Die eingecheckten Schaltungen und insbesondere
`FetchDecodeControls` blieben unverändert.

`ACC_LOAD` ist in beiden Läufen während `LOAD_CONST(23)` logisch `1`, und `CLK`
folgt in beiden Läufen phasengleich dem angelegten Takt. `VALID_IN` unterscheidet
sich dagegen bereits vor der ersten steigenden Flanke: Der eigenständige Kern
führt dort `1`, der eingebettete Systemkern `0`. Nach der Flanke übernimmt das
Akkumulatorwertregister deshalb in beiden Läufen `0x0017`, während nur der
eigenständige Kern auch das Gültigkeitsbit setzt. Damit sind Ladefreigabe,
Taktpfad und beide Register als gemeinsamer Reparaturort ausgeschlossen.

Gemäß Stop-Regel wurde noch keine Schaltung geändert. Der erste benannte
Unterschied liegt am `Datapath.VALID_IN`-Eingang. Als nächster enger Schritt
wird ausschließlich dessen Quelle `Operations.RESULT_IS_VALID` im
eingebetteten und eigenständigen Lauf verglichen. Erst wenn Quelle und Eingang
voneinander abweichen, darf die Leitung repariert werden; andernfalls wird die
Gültigkeitserzeugung für `LOAD_CONST` innerhalb von `Operations` weiter
verfolgt.

Dieser Quellenvergleich ist auf Ausgangs-Commit `09e5b38` erfolgt. Eine nur
unter `/tmp/ap18-result-valid/` instrumentierte Kopie führte
`Operations.RESULT_IS_VALID` und `Datapath.VALID_IN` über eindeutig benannte
Diagnoseausgänge bis in den unveränderten Fall `output-valid-write`; die
eingecheckten Schaltungen blieben unverändert. In allen acht Vektoren führen
beide Signale logisch `0`. Zwischen dem vermuteten Operations-Ausgang und dem
Datapath-Eingang ist damit in diesem Lauf kein Wertunterschied nachgewiesen,
sodass gemäß Stop-Regel keine Leitung geändert wurde.

Der Befund korrigiert zugleich die bisherige Quellenannahme: Während
`LOAD_CONST(23)` ist kein arithmetischer Operationszweig aktiv, daher ist
`Operations.RESULT_IS_VALID=0` für sich genommen erwartbar und kann nicht die
Gültigkeit des unmittelbaren Ladebefehls liefern. Die statische Netzverfolgung
zeigt außerdem, dass `Datapath.VALID_IN` nicht am
`RESULT_IS_VALID`-Ausgang hängt, sondern derzeit dasselbe Netz wie
`Operations.OVERFLOW` und `ErrorFlags.SET_OVF` erreicht. Das belegt eine
verdächtige Integration, bestimmt aber noch nicht den korrekten Reparaturpfad:
Die dokumentierte Ladegültigkeits-Auswahl muss zunächst anhand ihrer benannten
Selektoren und tatsächlichen Bauteilports lokalisiert werden. Als nächster enger
Diagnoseschritt werden deshalb beim ersten `LOAD_CONST` ausschließlich der
Immediate-Gültigkeitswert, der `ACC_MEMORY_SELECT`-gesteuerte
Gültigkeitsmultiplexer und dessen Weiterleitung bis `Datapath.VALID_IN`
verfolgt. Erst der erste abweichende oder offene benannte Übergang darf
repariert werden.

Die angekündigte lokale Verfolgung ist auf Ausgangs-Commit `e4443f9`
abgeschlossen. Der unveränderte elektrische Systemfall scheitert weiterhin
zuerst an Vektor 4 mit `OUTPUT_PORT_VALUE=0x0000` und
`OUTPUT_PORT_VALID=0`. Die portbezogene Topologie zeigt nun eindeutig, dass
`Datapath.VALID_IN` am Ausgang `Operations.OVERFLOW` liegt, während
`Operations.RESULT_IS_VALID` auf einem getrennten Netz endet. Die in der
Integrationsbeschreibung benannten Stufen `ACC_MEMORY_VALID_SELECT`,
`ACC_NOT_VALID_SELECT` und `ACC_INPUT_VALID_SELECT` sind auf dem aktuellen
`TinyCPUMain` nicht vorhanden. Damit existiert auch kein
`ACC_MEMORY_SELECT`-gesteuerter Multiplexer mehr, der für `LOAD_CONST` den
konstant gültigen Immediate-Pfad auswählen könnte.

Dieser Befund benennt erstmals den fehlenden Übergang und den falschen
Ersatzpfad, rechtfertigt aber noch keine Änderung anderer Netze. Das nächste
enge Reparaturpaket stellt ausschließlich die dokumentierte
Ladegültigkeits-Auswahl vor `Datapath.VALID_IN` wieder her. Seine erste
elektrische Abnahme ist `LOAD_CONST(23)` mit `VALID_IN=1`; erst danach wird der
unveränderte Fall `output-valid-write` erneut ausgeführt. Datenwert, Decoder,
`Operations`, Export, Ausgabeport, Interruptsteuerung, PC-Pfad und die
geschützte Darstellung von `FetchDecodeControls` bleiben bis dahin
unverändert.

## Wiederherstellung der Ladegültigkeits-Auswahl

Die angekündigte Reparatur stellt die drei benannten, ein Bit breiten Stufen
`ACC_MEMORY_VALID_SELECT`, `ACC_NOT_VALID_SELECT` und
`ACC_INPUT_VALID_SELECT` wieder her. Nur ihr Ausgang erreicht nun
`Datapath.VALID_IN`; die falsche Verbindung vom Überlaufausgang wurde
entfernt. `FetchDecodeControls` selbst blieb unverändert. Ein fokussierter
elektrischer Messpin in einer Kopie unter `/tmp` bestätigt vor der ersten
steigenden Flanke des Falls `output-valid-write` `VALID_IN=1`. Die
vollständige elektrische Kernmatrix bleibt mit allen 61 Fixtures grün.

Der erneut ausgeführte Systemfall übernimmt an Vektor 4 den Portwert und
dessen Gültigkeit dennoch weiterhin nicht. Damit ist die dokumentierte
Ladegültigkeits-Auswahl repariert, aber die Systemabnahme noch nicht
freigegeben. Als nächstes wird ausschließlich geprüft, ob das eingebettete
`Datapath.ACC_VALID_OUT` das an der ersten Flanke anliegende `VALID_IN=1`
speichert und bis zum Store-Zyklus hält.

## Topologische Nachprüfung nach der manuellen Neuverdrahtung

Die manuell neu gezeichnete Leitungsgruppe vor `Datapath.VALID_IN` hatte die
drei semantischen Multiplexerbezeichner verloren. Außerdem führte die
Immediate-Quelle `0` statt `1`, und der Select-Eingang von
`ACC_NOT_VALID_SELECT` endete auf dem benachbarten Decoder-Netz statt auf
`INVERT`. Die Nachprüfung hat ausschließlich diese drei Eigenschaften
korrigiert: Die vorhandenen Multiplexer tragen wieder ihre dokumentierten
Namen, die Immediate-Konstante ist `1`, und die Leitung endet über einen
expliziten Knickpunkt auf dem bereits vorhandenen `INVERT`-Netz. Die
Anordnung von `FetchDecodeControls` blieb unverändert.

Der semantische Offline-Prüfer verfolgt danach alle zehn Übergänge der
Ladegültigkeits-Auswahl erfolgreich; auch die allgemeinen Prüfungen auf offene
Unterblattanschlüsse, Mehrfachtreiber, Busbreiten und implizite Kontakte sind
grün. Der anschließend ausgeführte erste elektrische Systemfall reproduziert
weiterhin an Vektor 4 `OUTPUT_PORT_VALUE=0x0000` und
`OUTPUT_PORT_VALID=0`. Zusammen mit dem bereits belegten direkten Export von
`Datapath.ACC_VALID_OUT` nach `EXTERNAL_WRITE_VALID` schließt das das nächste
dokumentierte Paket ab: Das eingebettete Gültigkeitsregister hält bis zum
Store-Zyklus weiterhin `0`; der Fehler liegt nicht mehr in der nun
topologisch vollständigen Auswahl oder im Exportpfad.

Als nächstes enges Diagnosepaket werden deshalb ausschließlich die
Registersteueranschlüsse `ACC_LOAD`, `VALID_IN`, `CLK` und `RESET` direkt an
der eingebetteten `Datapath`-Instanz um die erste steigende Flanke verglichen.
Weitere Decoder-, Daten-, Speicher-, Port- und Interruptnetze bleiben bis zu
diesem Nachweis unverändert.

## Elektrische Nachprüfung des Akkumulator-Gültigkeitsregisters

Die angekündigte Messung wurde an einer ausschließlich unter
`/tmp/ap18-datapath-pin-check/` instrumentierten Kopie des Systemfalls
`output-valid-write` durchgeführt. Vor der ersten steigenden Flanke liegen
`ACC_LOAD=1` und `VALID_IN=1` an; der Datapath sieht denselben Takt wie der
Testvektor. Unmittelbar nach der Flanke ist `ACC_VALID_OUT=1`, und der Zustand
bleibt im folgenden Store-Zyklus gesetzt. An diesen vier Pfaden wurde deshalb
keine Schaltungsänderung vorgenommen.

Die weitergehende Anschlussmessung hat den ersten nachgelagerten Unterschied
am öffentlichen CPU-Adresspfad lokalisiert: Während Schreibwert `0x0017`,
Schreibgültigkeit und Schreibfreigabe korrekt anliegen, führt
`CPUIntegrationBoundary.ADDRESS=0x001` statt der für
`STORE_ADDRESS(0xfff)` erwarteten Adresse `0xfff`. Der Ausgabeport wird daher
nicht ausgewählt. Als nächstes enges Paket wird ausschließlich
`EffectiveAddress.EFFECTIVE_MEMORY_ADDRESS` gegen `TinyCPUMain.ADDRESS` und
die 16-auf-12-Bit-Auswahl in `CPUIntegrationBoundary` elektrisch verglichen.

## Elektrischer Vergleich des CPU-Adressexports

Die angekündigte Messung ist mit temporären Diagnosekopien des Falls
`output-valid-write` abgeschlossen. Bereits
`EffectiveAddress.EFFECTIVE_MEMORY_ADDRESS` und der direkt damit verbundene
öffentliche 16-Bit-Ausgang `TinyCPUMain.ADDRESS` führen `0x0001` statt der für
`STORE_ADDRESS(0xfff)` erwarteten Adresse. Hinter dem 16-auf-12-Bit-Splitter
der `CPUIntegrationBoundary` liegt entsprechend `0x001` an. Der Splitter
verändert den niederwertigen Wert somit nicht und ist kein belegter
Reparaturort; die eingecheckten Schaltungen blieben unverändert.

Als nächstes enges Paket werden ausschließlich die Operanden- und
Auswahleingänge von `EffectiveAddress` für den direkten Store-Modus bis zu
`EFFECTIVE_MEMORY_ADDRESS` elektrisch verglichen. Alle nachgelagerten
Adress-, Speicher- und Portpfade sowie Decoder-, Daten-, Gültigkeits- und
Interruptnetze bleiben bis zu diesem Nachweis unverändert.

## Elektrischer Vergleich der effektiven Adressbildung

Die begrenzte Messung am unveränderten Fall `output-valid-write` ist
abgeschlossen. Während `STORE_ADDRESS(0xfff)` sind die beiden
Registerauswahlen inaktiv, aber am direkten 16-Bit-Operanden von
`EffectiveAddress` liegt bereits `0x0001` statt `0x0fff`. Der Baustein gibt
diesen ausgewählten Wert erwartungsgemäß unverändert als
`EFFECTIVE_MEMORY_ADDRESS=0x0001` aus. Register-, Offset- und Ausgangspfad sind
damit nicht der erste Fehlerort und wurden nicht verändert.

Als nächstes enges Paket wird ausschließlich der unmittelbare
Instruktionsoperand vom 16-Bit-Splitterzweig bis
`EffectiveAddress.DIRECT_ADDR` verfolgt. Alle anderen Decoder-, Auswahl-,
Adress-, Speicher-, Port-, Daten-, Gültigkeits- und Interruptpfade bleiben bis
zu diesem Nachweis unverändert.

## Elektrische Prüfung des unmittelbaren Instruktionsoperanden

Die angekündigte Messung wurde am unveränderten `STORE_ADDRESS(0xfff)` mit
einer ausschließlich unter `/tmp` instrumentierten Kopie durchgeführt. Das
22-Bit-Instruktionswort liegt als `0x29ffff` am Splittereingang an. Der
Opcode-Zweig führt `0x29`; der aus den Bits 0 bis 15 gebildete Operandenzweig
führt `0xffff`. Derselbe Wert liegt am topologisch direkt verbundenen Eingang
`EffectiveAddress.DIRECT_ADDR` an. Splitterzuordnung und Leitung bis zu diesem
Eingang sind damit nicht der erste Fehlerort; die eingecheckte Schaltung wurde
nicht verändert.

Der bisherige Befund `DIRECT_ADDR=0x0001` ist damit als falsche Zuordnung eines
temporären Messpunkts korrigiert. Der öffentliche Adressausgang bleibt im
fokussierten Lauf dennoch `0x0001`. Als nächstes enges Diagnosepaket werden
deshalb ausschließlich die beiden Auswahlsteuersignale und die vier benannten
16-Bit-Eingänge von `EffectiveAddress` an den tatsächlichen Symbolanschlüssen
mit dem internen Ausgang des ersten und zweiten Multiplexers verglichen. Erst
ein dort belegter erster Unterschied darf eine Änderung der Auswahlverdrahtung
auslösen. Danach folgt als separates Paket die erneute Ausführung des ersten
Systemfalls; alle Speicher-, Port-, Daten-, Gültigkeits- und Interruptpfade
bleiben bis dahin unverändert.

## Elektrischer Vergleich der effektiven Adressauswahl

Der angekündigte Vergleich ist auf Ausgangs-Commit `bf53d59` mit paarweise
verschiedenen Eingangswerten erfolgt. Beim direkten Store führen
`DIRECT_ADDR=0xffff`, `REG_ADDR=0x0014`, `OFFSET_ADDR=0x0015` und
`REG_SELECTED=0x0001`; beide Auswahlsteuersignale sind `0`. Der erste
Multiplexer liefert korrekt `EFFECTIVE_REGISTER_SELECTED_OUT=0xffff`. Der
zweite Multiplexer liefert dagegen `EFFECTIVE_MEMORY_ADDRESS=0x0001`, weil
sein unselektierter Dateneingang unmittelbar vom eigenständigen öffentlichen
Eingang `REG_SELECTED` und nicht vom Ausgang des ersten Multiplexers gespeist
wird. Damit ist der erste elektrische Unterschied zwischen den beiden
Multiplexerstufen benannt; Eingänge, Selektoren und die erste Stufe sind kein
Reparaturort.

Die Diagnose ist als eigener Fall im elektrischen Effective-Address-Lauf
festgehalten. Sie verwendet absichtlich verschiedene Werte, damit die bisher
gleichen Fixture-Werte den fehlenden Übergang nicht länger verdecken. Gemäß
Stop-Regel wurde die Schaltung in diesem Paket nicht geändert. Als nächstes
wird ausschließlich der Datenübergang vom Ausgang der ersten zur
unselektierten Datenseite der zweiten Multiplexerstufe repariert. Anschließend
folgen getrennt zuerst die Effective-Address-Abnahme, dann
`output-valid-write` und erst bei dessen Erfolg die vollständige Systemmatrix.

## Reparatur des Übergangs zwischen den Adressmultiplexern

Der elektrisch belegte Übergangsfehler ist nun minimal in `EffectiveAddress`
repariert. Der Ausgang der ersten Multiplexerstufe führt direkt auf den
unselektierten Dateneingang der zweiten Stufe; `REG_SELECTED` erreicht nur noch
deren Offset-Zweig. Der bisherige externe Rückweg über `OFFSET_ADDR` ist aus
dem aktiven Datenpfad entfernt. `FetchDecodeControls` und alle übrigen
Daten-, Speicher-, Port- und Interruptpfade blieben unverändert.

Der isolierte elektrische Regressionsfall verwendet weiterhin
`DIRECT_ADDR=0xffff` und den unterscheidbaren Wert `REG_SELECTED=0x0001` und
liefert jetzt durch beide Stufen `0xffff`. Der autonome Kernlauf besteht
weiterhin zweimal. Die anschließend vorschriftsmäßig zuerst ausgeführte
Systemfixture `output-valid-write` ist noch nicht grün: Bereits ihr erster
Vektor meldet sämtliche sieben öffentlichen Systemzustände als oszillierend.
Die vollständige Systemmatrix wurde deshalb nicht geöffnet. Als nächstes wird
ausschließlich diese neu benannte Oszillation an der Systemgrenze eingegrenzt;
die reparierte Adressauswahl wird nicht ohne einen abweichenden benannten Port
wieder verändert.

## Eingrenzung der Oszillation auf den Effective-Address-Übergang

Der reproduzierte Systemfall `output-valid-write` oszilliert nicht aufgrund
der Peripherie oder des 16-auf-12-Bit-Adapters. Ein historischer Vergleich mit
dem Stand unmittelbar vor der Adressmultiplexer-Reparatur liefert bis Vektor 3
stabile Systemausgänge und erst danach den bereits bekannten falschen
Ausgabewert. Mit der reparierten `EffectiveAddress`-Schaltung oszillieren die
sieben öffentlichen Systemzustände dagegen bereits ab Vektor 1.

Der erste Standunterschied, der die Oszillation aktiviert, ist damit auf den
neu eingefügten Übergang zwischen den beiden Effective-Address-Multiplexern
und dessen unmittelbare Hauptblattanschlüsse begrenzt. Der isolierte
Effective-Address-Fall und der autonome Kernlauf bleiben grün; daraus darf
weder ein Fehler des Multiplexers noch ein Fehler der Peripherie abgeleitet
werden. Insbesondere ist die gemeinsame Meldung aller sieben öffentlichen
Zustände nur Logisims Folge des nicht einschwingenden Gesamtnetzes und kein
Nachweis von sieben unabhängigen Registerfehlern.

Gemäß Stop-Regel wurde diese Grenze in diesem Diagnosepaket nicht umverdrahtet.
Als nächstes enges Diagnosepaket werden ausschließlich
`EFFECTIVE_REGISTER_SELECTED_OUT`, `EFFECTIVE_MEMORY_ADDRESS`, der öffentliche
Kernpin `ADDRESS` und der 12-Bit-Adresspin der `CPUIntegrationBoundary` im
ersten Vektor verglichen. Erst der erste dort tatsächlich oszillierende
benannte Übergang darf repariert werden; der isoliert korrekte
Multiplexerübergang wird nicht allein aufgrund dieses A/B-Befunds
zurückgenommen.

## Wiederherstellung der Immediate-Ladegültigkeit nach der Neuanordnung

Vor dem angekündigten elektrischen Vergleich der vier Adresssignale hat das
verpflichtende Offline-Gate einen neuen, engeren Vertragsbruch erkannt: Die
Immediate-Konstante der bereits dokumentierten Ladegültigkeits-Auswahl trug
nach der manuellen Neuanordnung wieder den Logisim-Defaultwert `0`. Nur dieses
Attribut wurde auf den zuvor elektrisch belegten Wert `1` zurückgesetzt.
`FetchDecodeControls` sowie Adress-, Speicher-, Port- und Interruptnetze
blieben unverändert. Der Offline-Lauf besteht danach wieder vollständig.

Der anschließend erneut ausgeführte Fall `output-valid-write` meldet weiterhin
ab Vektor 1 alle sieben öffentlichen Systemzustände als oszillierend. Die
Korrektur der unabhängigen Ladegültigkeitsregression ist daher keine
Systemfreigabe; die vollständige Systemmatrix bleibt geschlossen. Das nächste
enge Diagnosepaket bleibt der bereits angekündigte Vergleich von
`EFFECTIVE_REGISTER_SELECTED_OUT`, `EFFECTIVE_MEMORY_ADDRESS`, dem öffentlichen
Kernpin `ADDRESS` und dem 12-Bit-Adresspin der `CPUIntegrationBoundary`.

## Ursache der Systemoszillation

Die angekündigte hierarchische Messung wurde mit dem ersten Vektor von
`output-valid-write` durchgeführt. Entgegen der bisherigen Eingrenzung sind
alle vier Adresssignale stabil: `EFFECTIVE_REGISTER_SELECTED_OUT`,
`EFFECTIVE_MEMORY_ADDRESS` und der öffentliche Kernpin `ADDRESS` führen
`0x0017`; der 12-Bit-Ausgang der `CPUIntegrationBoundary` führt entsprechend
`0x017`. Keiner dieser Punkte gehört zu Logisims Oszillationsmenge. Die
Effective-Address-Reparatur ist daher nicht der oszillierende Übergang.

Die Oszillationsmenge beginnt stattdessen an den beiden externen
Speicherrückführungen. `CPUIntegrationBoundary` verwendet derzeit
`PRINT_ADDRESS_VALUE` und `PRINT_ADDRESS_VALID` als vermeintliche rohe
RAM-Leseausgänge. Diese Signale liegen aber bereits **hinter** den beiden vom
Systemmodus aktivierten externen Speichermultiplexern. Dadurch entstehen zwei
rein kombinatorische Schleifen:

```text
EXTERNAL_MEMORY_VALUE_SELECT -> PRINT_ADDRESS_VALUE
  -> CPUIntegrationBoundary.RAM_READ_VALUE
  -> OutputMemoryPath.READ_VALUE
  -> CPUIntegrationBoundary.READ_VALUE
  -> TinyCPUMain.EXTERNAL_MEMORY_VALUE
  -> EXTERNAL_MEMORY_VALUE_SELECT

EXTERNAL_MEMORY_VALID_SELECT -> PRINT_ADDRESS_VALID
  -> CPUIntegrationBoundary.RAM_READ_VALID
  -> OutputMemoryPath.READ_VALID
  -> CPUIntegrationBoundary.READ_VALID
  -> TinyCPUMain.EXTERNAL_MEMORY_VALID
  -> EXTERNAL_MEMORY_VALID_SELECT
```

Logisim meldet folgerichtig die beiden Selektoren, die Ein- und Ausgänge der
Speichergrenzen sowie die davon abhängigen Operations-Signale als
oszillierend. Die sieben öffentlichen Systemzustände sind nur nachgelagerte
Fehlermeldungen des nicht eingeschwungenen Top-Levels.

Gemäß Stop-Regel wurde die Schaltung in diesem Diagnosepaket nicht verändert.
Das nächste Reparaturpaket muss ausschließlich rohe `Memory.MEMORY_DATA`- und
`Memory.MEMORY_VALID`-Signale vor den externen Selektoren aus dem Kern
exportieren und diese beiden neuen Ausgänge statt der nachselektierten
`PRINT_ADDRESS_*`-Signale an die RAM-Leseseite der
`CPUIntegrationBoundary` anschließen. Danach werden zuerst
`output-valid-write` und erst bei dessen Erfolg die übrigen Systemfälle
ausgeführt.

## Reparatur der oszillierenden Speicherrückführung

Der Kern exportiert `Memory.MEMORY_DATA` und `Memory.MEMORY_VALID` nun als
eigene Ausgänge `RAW_MEMORY_VALUE` und `RAW_MEMORY_VALID` unmittelbar vor den
externen Speicherselektoren. `CPUIntegrationBoundary` verwendet ausschließlich
diese beiden Rohsignale für `READ_VALUE` und `READ_VALID`; die bisherigen
Rückwege über die bereits nachselektierten `PRINT_ADDRESS_*`-Signale entfallen.
Damit enthält der Systemdatenpfad keine kombinatorische Selbstrückführung mehr.

Der Vertrag benennt die neuen Kernpins und ihre direkten Speicherpfade. Der
Prüfer leitet sämtliche Anschlüsse der generierten Kernbox jetzt aus den
Pinbezeichnungen statt aus festen Zeilenpositionen ab. Ein Mutationstest trennt
jeden Rohspeicherexport einzeln und belegt, dass die Regression erkannt wird.

Der zuerst wiederholte Fall `output-valid-write` besteht elektrisch und zeigt
damit, dass die Oszillation behoben ist. Die anschließend geöffnete Matrix
stoppt regelkonform beim nächsten Fall `output-invalid-write`: Ab Vektor 8
liefert `OUTPUT_PORT_VALUE` den Wert `0x0014` statt des zu haltenden Werts
`0x0017`; eine Oszillation wird nicht mehr gemeldet. Das nächste enge
Diagnosepaket verfolgt deshalb ausschließlich Schreibwert, Schreibgültigkeit
und Schreibfreigabe dieses ungültigen Schreibversuchs bis zum
`OutputPort`-Register. Die übrigen Systemfälle bleiben bis zu diesem Befund
geschlossen.

# TinyCPU-Peripherie: sichtbarer Maschinenvertrag

Dieses Dokument beschreibt zuerst das **beobachtbare Verhalten** der
Peripherie. Die Logisim-Schaltung ist eine Implementierung dieses Vertrags und
nicht selbst dessen Spezifikation.

## Status und bewusste Grenze

`TinyCPU_Peripherals.circ` enthält derzeit drei eigenständig prüfbare
Bausteine: `OutputPort`, `OutputMemoryPath` und `InterruptController`. Die neue
`CPUIntegrationBoundary` friert zusätzlich die dafür benötigte CPU-seitige
Daten-, Befehls- und PC-Schnittstelle mit Richtung und Breite ein.
`TinyCPUSystemMain` beschreibt nur die öffentliche Systemgrenze. Takt, Reset
und externe Interruptanforderung erreichen inzwischen die jeweils betroffenen
Bausteine. Hinter der neuen Grenze sind der atomare Leseweg aus RAM-Wert und
RAM-Gültigkeit, der 12-Bit-Adressweg und die drei CPU-seitigen Signale für
Schreibwert, Schreibgültigkeit und Schreibfreigabe von vorläufigen
CPU-Kernanschlüssen bis zur Speichergrenze direkt verdrahtet. Auch die
Instruktionsgrenze und die drei Befehlsimpulse für Aktivierung, Deaktivierung
und Rückkehr reichen direkt zu den Interruptausgängen. Der Folge-PC wird von
einem vorläufigen Kernanschluss direkt zur Interruptsteuerung geführt. Damit
ist der PC-Steuerpfad innerhalb der Grenze ebenfalls vorbereitet; die
Top-Level-Grenze ist nun mit allen 15 Daten-, Adress-, Schreib-, Befehls- und
Interruptpfaden direkt an `OutputMemoryPath` und `InterruptController`
angeschlossen. Für alle direkten 1:1-Übergaben zwischen `TinyCPUMain`,
`CPUIntegrationBoundary` und `InterruptController` gilt dabei dasselbe
Pin-Schema: Name und Busbreite bleiben an beiden Seiten identisch; nur die
Richtung kehrt sich an der Verbrauchergrenze um. Das betrifft insbesondere
`INTERRUPT_TARGET_PC` sowie die drei `*_INTERRUPTS_REQUEST`-Signale.
Der 12-Bit-Ausgang `CPUIntegrationBoundary.ADDRESS` endet ausschließlich am
12-Bit-Eingang `OutputMemoryPath.ADDRESS`. Er darf insbesondere nicht mit dem
16-Bit-Eingang `OutputMemoryPath.RAM_READ_VALUE` verbunden werden. Die
Vertragsprüfung vergleicht deshalb für jede direkte Übergabe ausdrücklich
Erzeugerpin, Verbraucherpin, Richtung und Breite, statt nur zu prüfen, ob eine
Leitung optisch an einem Unterbaustein endet.
Die Prüfung dieser Wege folgt den benannten Pins und den
tatsächlichen Anschlüssen der generierten Symbole und bleibt dadurch auch nach
einer manuellen Neuanordnung der Grenze wirksam.
Innerhalb der Grenze speisen außerdem der adressierte Speicherwert des
vollständigen Kerns und dessen Gültigkeitsbit direkt die beiden
Leseausgänge des Adapters. Die ausgewählte Rückleseseite erreicht nun die neue
additive Kernschnittstelle aus Wert, Gültigkeit und Aktivierung. Ihre interne
Auswahl ist nun für Wert und Gültigkeit jeweils über einen eigenen Multiplexer
verdrahtet. `USE_EXTERNAL_MEMORY` schaltet beide Pfade gemeinsam auf die
Systemrückleseseite; ohne diese additive Aktivierung bleibt der bisherige
RAM-Pfad des eigenständigen 1.0-Profils unverändert ausgewählt.
Deshalb
ist der klassische Interruptcontroller vorläufig eine **Referenzlösung für
AP 18**, keine unumkehrbare Festlegung der TinyCPU-Architektur.

Insbesondere sind Polling, ein ausdrücklicher `WAIT`-Befehl und ein lediglich
sichtbares Pending-Bit weiterhin denkbare Alternativen. Erst die spätere
Systemintegration entscheidet, ob der automatische Sprung wirklich Bestandteil
der TinyCPU werden soll.

## Ausgabeport: eine besondere Speicheradresse

Adresse `0xfff` gehört im Peripherieprofil nicht zum RAM, sondern zum
16-Bit-Ausgabeport. Für jede andere Adresse bleibt das normale RAM-Verhalten
erhalten.

Mit `OUTPUT_ADDRESS := (ADDRESS = 0xfff)` gilt:

```text
RAM_WRITE_ENABLE  = WRITE_ENABLE AND NOT OUTPUT_ADDRESS
PORT_WRITE_ENABLE = WRITE_ENABLE AND OUTPUT_ADDRESS
```

Ein Portzugriff darf nur einen gültigen Schreibwert übernehmen:

```text
ACCEPTED_WRITE = PORT_WRITE_ENABLE AND WRITE_VALID
```

Bei `ACCEPTED_WRITE = 1` werden Wert und Gültigkeit gemeinsam übernommen. Bei
Reset werden beide gelöscht; andernfalls halten sie ihren Zustand. Lesen von
`0xfff` liefert Portwert und Portgültigkeit, Lesen jeder anderen Adresse den
RAM-Wert und dessen Gültigkeit. Ein Schreiben nach `0xfff` darf niemals
zusätzlich das RAM verändern.

`OutputMemoryPath` ist damit nur ein Adressverteiler: `0xfff` führt zum
Ausgabeport, alle übrigen Adressen führen zum RAM.

## Interrupt als explizite Pseudo-Instruktion

Die Referenzlösung darf als ein von außen ausgelöster, automatischer Aufruf
verstanden werden. Sie bestimmt **nicht**, was die Interruptroutine tut. Das
Programm ab Adresse `0xff0` bestimmt die Reaktion auf das Ereignis.

Eine steigende Flanke an `INTERRUPT_REQUEST` setzt `INTERRUPT_PENDING`. Die
Anforderung wird ausschließlich zwischen zwei Instruktionen angenommen:

```text
INTERRUPT_ACCEPT =
    INTERRUPT_PENDING
    AND INTERRUPT_ENABLED
    AND INSTRUCTION_BOUNDARY
    AND NOT IN_INTERRUPT_HANDLER
```

Bei der Annahme führt die Maschine semantisch folgende Pseudo-Instruktion aus:

```text
RET_ADDR       := NEXT_PC
RET_ADDR_VALID := 1
IN_INTERRUPT_HANDLER := 1
INTERRUPT_ENABLED    := 0
INTERRUPT_PENDING    := 0
TARGET_PC            := 0xff0
```

`NEXT_PC` ist die Adresse der noch nicht ausgeführten nächsten Instruktion,
nicht die Adresse der soeben abgeschlossenen Instruktion. Dadurch wird nach der
Interruptroutine an der richtigen Stelle weitergearbeitet.

## Rückkehr

Eine Rückkehr ist nur gültig, wenn alle drei Bedingungen erfüllt sind:

```text
VALID_RETURN =
    RETURN_REQUEST
    AND IN_INTERRUPT_HANDLER
    AND RET_ADDR_VALID
```

Bei einer gültigen Rückkehr gilt:

```text
TARGET_PC            := RET_ADDR
RET_ADDR_VALID := 0
IN_INTERRUPT_HANDLER := 0
INTERRUPT_ENABLED    := 1
```

Ein `RETURN_FROM_INTERRUPT_REQUEST` außerhalb eines aktiven Handlers oder ohne gültige
Rückkehradresse setzt `ILL_RET`. Verschachtelte Interrupts sind in dieser
Referenzlösung ausdrücklich nicht vorgesehen.

Kurz gesagt:

```text
Interruptannahme = automatischer CALL nach 0xff0
gültige Rückkehr = automatisches RETURN zu NEXT_PC
```

Die Instruktionen ab `0xff0` sind normale TinyCPU-Instruktionen im Speicher.
Sie sind nicht Bestandteil des Interruptcontrollers und müssen vom jeweiligen
Programm bereitgestellt werden.

## Sichtbare Zustände

Die Zustände sind nicht als geheime interne Regeln zu verstehen. Das
Systemprofil und der Debug-Trace machen sie ausdrücklich sichtbar:

- `OUTPUT_PORT_VALUE` und `OUTPUT_PORT_VALID`;
- `INTERRUPT_ENABLED` und `INTERRUPT_PENDING`;
- `IN_INTERRUPT_HANDLER`;
- `RET_ADDR` und `RET_ADDR_VALID`.

Diese Sichtbarkeit ist eine didaktische Anforderung: Ein Trace muss erklären
können, warum die Referenzmaschine einen Interrupt annimmt, nach `0xff0`
springt oder eine Rückkehr ablehnt.

## Reset und Priorität

Reset löscht Ausgabezustand, Pending-Bit, Maske, Handlerzustand und
Rückkehrzustand. Treffen mehrere Ereignisse an derselben Taktflanke zusammen,
gilt:

1. Reset;
2. Interruptannahme;
3. normale Instruktionsverarbeitung.

Diese Regeln sind die Grundlage für Softwaremodell, Verträge und spätere
elektrische Systemtests. Die Systemschaltung bindet inzwischen die
unveränderte `TinyCPUMain`-CPU als externe Projektbibliothek in ihre
Integrationsgrenze ein. Der Kern exportiert inzwischen Schreibwert,
Schreibgültigkeit und Schreibfreigabe direkt von den drei Netzen, die auch
seinen bisherigen RAM-Schreibpfad speisen. Die Interrupt-Rückkopplung ist nun vollständig elektrisch angebunden:
`INTERRUPT_ACCEPT` wählt im Fetchpfad mit Vorrang `INTERRUPT_TARGET_PC` als nächsten
Programmzähler, und `ILL_RET` setzt das vorhandene Sticky-Flag
`ERROR_ILL`. Damit enden die drei Rückleitungen nicht mehr unverbunden an der
Integrationsgrenze. `CORE_ADDRESS` und `RAM_WRITE_ENABLE` bleiben dagegen
vorläufige Adaptereingänge; die eigenständigen Bausteine sind deshalb noch
kein Nachweis einer vollständigen CPU-Integration.

Die übrigen Übergaben sind jetzt nach der tatsächlich von Logisim erzeugten
Portreihenfolge verdrahtet. Das ist insbesondere wichtig, weil der Anker einer
Unterbaugruppe nicht automatisch ihr erster Eingang ist: Eingänge liegen links,
Ausgänge rechts und werden jeweils nach ihrer Position im Unterblatt sortiert.
Die Abnahme kombiniert deshalb vier voneinander unabhängige Kontrollen:
Vertrags- und Pfadprüfung mit Leitungs-Mutationstests, Breiten- und
Mehrfachtreiberprüfung, geometrischen Kontakt-Audit sowie einen headless
Logisim-Tabellenlauf. Damit werden falscher Port, fehlendes Leitungsstück,
Kurzschluss und ein in Logisim undefinierter Wert getrennt sichtbar. Ein
absoluter mathematischer Beweis für alle zeitlichen Abläufe ist das noch nicht;
der vollständige End-to-End-Nachweis bleibt von der Anbindung der beiden
vorläufigen Adaptereingänge und der elektrischen Systemmatrix abhängig.

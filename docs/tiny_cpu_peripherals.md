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
CPU-Kernanschlüssen bis zur Speichergrenze direkt verdrahtet; Befehls- und
PC-Steuerpfade sowie die Top-Level-Verdrahtung sind noch nicht eingefügt. Die
Prüfung dieser Wege folgt den benannten Pins und bleibt dadurch auch nach einer
manuellen Neuanordnung der Grenze wirksam.
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
RETURN_ADDRESS       := NEXT_PC
RETURN_ADDRESS_VALID := 1
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
    AND RETURN_ADDRESS_VALID
```

Bei einer gültigen Rückkehr gilt:

```text
TARGET_PC            := RETURN_ADDRESS
RETURN_ADDRESS_VALID := 0
IN_INTERRUPT_HANDLER := 0
INTERRUPT_ENABLED    := 1
```

Ein `RETURN_REQUEST` außerhalb eines aktiven Handlers oder ohne gültige
Rückkehradresse setzt `ILLEGAL_RETURN`. Verschachtelte Interrupts sind in dieser
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
- `RETURN_ADDRESS` und `RETURN_ADDRESS_VALID`.

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
elektrische Systemtests. Die eigenständigen Bausteine allein sind noch kein
Nachweis einer vollständigen CPU-Integration.

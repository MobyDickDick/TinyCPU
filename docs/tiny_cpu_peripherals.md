# TinyCPU-Peripherie: sichtbarer Maschinenvertrag

Dieses Dokument beschreibt zuerst das **beobachtbare Verhalten** der
Peripherie. Die Logisim-Schaltung ist eine Implementierung dieses Vertrags und
nicht selbst dessen Spezifikation.

## Status und bewusste Grenze

Die optionale Systemvariante `tinycpu-peripherals-16-12-v1` ist auf dem
16/12-Kern implementiert. [TinyCPU_Peripherals.circ](../hardware/logisim/TinyCPU_Peripherals.circ)
verbindet den Kern über `CPUIntegrationBoundary` mit `OutputMemoryPath`,
`OutputPort` und `InterruptController`. RAM-Rücklesewert und Gültigkeit,
Schreibwert/-gültigkeit/-freigabe, Adresse, Instruktionsgrenze, Interruptbefehle
und Folge-PC sind an die benannten Kernpins angeschlossen. Interruptannahme,
Ziel-PC und ungültige Rückkehr wirken auf den Kern zurück.

Im eigenständigen Kern bleibt der interne RAM-Pfad aktiv; der externe Modus
wählt Wert und Gültigkeit gemeinsam. Für direkte Übergaben gelten gleiche
Signalnamen und Breiten bei entgegengesetzter Pinrichtung. Die 12-Bit-Adresse
endet am Adresseingang, nicht am 16-Bit-Rücklesewert.

Alle sieben versionierten Systemfälle bestehen in der
[lokalen Abnahme vom 10. November](tiny_cpu_input_reset_repair.md). Sie prüfen
Ausgabeport, Interruptannahme/-rückkehr, Maskierung und Reset gemäß dem
[Systemvertrag](../hardware/logisim/tinycpu-system-trace-v1.json). Diese
optionale Referenzlösung ist kein Bestandteil des Basis-Maschinenformats;
die neue Releaseabnahme und der manuelle GUI-Test bleiben offen.
Historische Integrationsschritte stehen im [AP-18-Plan](tiny_cpu_peripherals_plan.md).

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
    (INTERRUPT_PENDING OR RISING_EDGE_DETECT)
    AND INTERRUPT_ENABLED
    AND INSTRUCTION_BOUNDARY
    AND NOT IN_INTERRUPT_HANDLER
```

Eine aktuelle steigende Anforderung kann damit bereits an derselben
Instruktionsgrenze angenommen werden. Bei gesperrter Maske bleibt die
Anforderung im Pending-Zustand erhalten. Reset hat Vorrang.

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
RET_ADDR             := 0
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

Diese Regeln bilden die Grundlage für Softwaremodell, Verträge und die
implementierten elektrischen Systemtests. Die Systemschaltung bindet inzwischen die
unveränderte `TinyCPUMain`-CPU als externe Projektbibliothek in ihre
Integrationsgrenze ein. Der Kern exportiert inzwischen Schreibwert,
Schreibgültigkeit und Schreibfreigabe direkt von den drei Netzen, die auch
seinen bisherigen RAM-Schreibpfad speisen. Die Interrupt-Rückkopplung ist nun vollständig elektrisch angebunden:
`INTERRUPT_ACCEPT` wählt im Fetchpfad mit Vorrang `INTERRUPT_TARGET_PC` als nächsten
Programmzähler, und `ILL_RET` setzt das vorhandene Sticky-Flag
`ERROR_ILL`. Damit enden die drei Rückleitungen nicht mehr unverbunden an der
Integrationsgrenze. `RAM_WRITE_ENABLE` wird über den externen Speichermodus bis
zum Schreibfreigabeeingang der `Memory`-FBox geführt; im eigenständigen
Kernbetrieb wählt derselbe Selektor weiterhin die interne Schreibanforderung.

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
der End-to-End-Nachweis gilt für die ausgeführten Fälle der elektrischen
Systemmatrix.

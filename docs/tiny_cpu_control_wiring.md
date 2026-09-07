# Verdrahtung ab `FetchDecodeControls`

Dieses Schema ist die Arbeitsgrundlage für die weitere Verdrahtung der
16/12-Schaltung `TinyCPU.circ`. Die eigenständige Variante
`TinyCPU-8-8.circ` bleibt dabei ausdrücklich unverändert.

## Grundsatz

`FetchDecodeControls` liefert zwei unabhängige Gruppen an `Operations`:

* genau eine Operationsfamilie (`ADD_OPERAND` bis `XOR_OPERAND`) und
* genau eine Argumentart (`CONST_ARGUMENT`, `ADDR_ARGUMENT`,
  `ADDR_REG_ARGUMENT` oder `ADDR_REG_OFFS_ARGUMENT`).

Es werden deshalb weder auf dem Hauptblatt noch an der Grenze von
`Operations` die 28 Kreuzprodukte `ADD_CONST` bis `XOR_REG_OFF` einzeln
geführt. Erst **innerhalb** von `Operations` bildet je ein UND-Gatter aus
Operationsfamilie und Argumentart das lokale Aktivierungssignal für den
vorhandenen Rechenzweig. Damit sind nur elf statt 28 Steuerleitungen über die
Blattgrenze zu führen.

## Datenwege

Die Argumentart ist ein Steuersignal und kein zweiter Datenweg. Der
16-Bit-Instruktionsoperand wird genau einmal als gemeinsamer Bus
`IMMEDIATE_VALUE` an `Operations` geführt. Daneben bleiben die gemeinsam
genutzten Busse `MEMORY_VALUE` und `ACC_VALUE` sowie `MEMORY_VALID` und
`ACC_VALID` bestehen.

Innerhalb jedes binären Rechenzweigs wählt `CONST_ARGUMENT`
`IMMEDIATE_VALUE`. Die drei anderen Argumentarten wählen denselben
`MEMORY_VALUE`; ihre Unterscheidung findet ausschließlich im zentralen
Adresspfad statt. So muss der konstante Operand nicht für jede Operation
separat eingefügt oder verdrahtet werden.

## Direkte Steuerungen

Laden, Speichern, Sprünge, Fehler, Ein-/Ausgabe und Halt bleiben direkte
Ausgänge von `FetchDecodeControls`. Sie werden nicht mit den beiden Gruppen
der binären Operationen gekreuzt. Insbesondere führen `LOAD_CONST` und die
drei speicherbasierten Ladeformen weiterhin in die gemeinsame
Akkumulator-Auswahl; `NOT` und `INPUT` bleiben nachgelagerte Auswahlstufen.

Die Ergebnispriorität lautet damit:

1. Ergebnis einer binären Operation,
2. unmittelbares Laden,
3. speicherbasiertes Laden,
4. `NOT`,
5. `INPUT` als letzte Überschreibung.

## Umsetzungsschritte in `TinyCPU.circ`

1. Die sieben Operations- und vier Argumentleitungen direkt von
   `FetchDecodeControls` bis zur linken Grenze von `Operations` legen.
2. In `Operations` die 28 lokalen UND-Verknüpfungen anlegen und deren Ausgänge
   mit den bereits vorhandenen Moduseingängen der sieben Rechenzweige
   verbinden.
3. Den Instruktionsoperanden, Speicherwert und Akkumulatorwert jeweils nur
   einmal als gemeinsamen Datenbus zuführen.
4. Erst nach der elektrischen Abnahme die alten 28 Top-Level-Steuerwege und
   ihre Übergangsproben entfernen.
5. `TinyCPU-8-8.circ` bei allen diesen Schritten auslassen; dessen bestehende
   Profilabnahme bleibt unverändert.

Die maschinenlesbare Fassung dieses Schemas liegt in
`hardware/logisim/tinycpu-control-wiring-v2.json`. Der Offline-Prüfer stellt
sicher, dass die dort genannten Gruppen vollständig und disjunkt sind, alle
28 lokalen Kombinationen entstehen und die 8/8-Datei ausgeschlossen bleibt.

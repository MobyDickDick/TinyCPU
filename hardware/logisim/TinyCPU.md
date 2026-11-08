# TinyCPU: Grundidee

Begleitbeschreibung zu [TinyCPU.circ](TinyCPU.circ).

## TinyCPUMain

Verbindet vier fachliche Bereiche mit den darin enthaltenen acht Funktionsboxen:
Befehle holen und dekodieren, Operanden
bereitstellen, rechnen, Ergebnisse speichern und den nächsten Befehl bestimmen. Die
öffentlichen Pins verbinden den Kern mit Takt, Speicher, Ausgaben und
Interruptsteuerung.

Die [Aufteilung der beiden Übersichten vom 8. November 2026](../../docs/tiny_cpu_main_modules_20261108.md)
ersetzt den verworfenen Zwischenstand durch Befehlsablauf, Compute, Speicher
und Status, verbunden über dokumentierte, sichtbar verdrahtete Busse.

## TinyCPUInputMain

Zusätzliche, ausdrücklich wählbare CPU-Grenze mit `INPUT_VALUE` (16 Bit),
`INPUT_VALID` und `INPUT_CONSUME`. Sie verwendet dieselben sechs übrigen
Funktionsboxen wie `TinyCPUMain`; nur Akkumulator und Fehlerlogik besitzen
Eingabevarianten. Die bisherige öffentliche CPU-Grenze bleibt erhalten.

## AccumulatorInputUnit

Erweitert die bestehende Akkumulatorbox um die Auswahl externer INPUT-Daten.
Ein gültiges Angebot lädt den angebotenen Wert; ein ungültiges Angebot lädt
kanonisch Null mit gelöschter Gültigkeit. `INPUT_CONSUME` folgt dem aktuellen
INPUT-Decode bei inaktivem Reset; jede steigende Taktflanke ist ein Leseversuch.
Der bisherige Datapath wird gemeinsam mit der Baseline verwendet.

## FaultInputUnit

Erweitert die Fehlerbox um `INPUT_VALID`. Ausschließlich ein INPUT mit
ungültigem Angebot setzt die INPUT-Fehlerursache; das gemeinsame `ErrorFlags`
speichert sie bis `CLEAR_ERROR`. Ein erfolgreicher INPUT löscht keine alten Flags.

Die [Abnahme der Eingabegrenze](../../docs/tiny_cpu_input_boundary.md) beschreibt
Reproduktion, Nachweise und die noch folgende dynamische Eingabeabnahme.

## EffectiveAddress

Wählt zwischen direkter Adresse, Adressregister und Adressregister plus Offset. Gibt
außerdem die gewählte Registervariante und eine Bereichsüberschreitung an die weitere
Adressprüfung weiter.

## Datapath

Speichert den 16-Bit-Akkumulatorwert und sein Gültigkeitsbit bei aktivem ACC_LOAD an der
Taktflanke. Ein Vergleich mit null liefert ZERO und NEGATIVE; DATAPATH_STARTUP_RESET
löscht bei 1 beide Register und liegt im CPU-Kern in der AccumulatorUnit dauerhaft auf
0, also inaktiv.

Im CPU-Kern wird der vorhandene Löscheingang durch die feste Null
nicht betätigt. Sie definiert den Ruhepegel dieses Steuereingangs und
kann nicht einfach entfallen. RESET der CPU setzt nach dem
bestehenden Vertrag den Befehlsablauf zurück, ohne diese Register zu löschen.

## AddressPath

Speichert die Basisadresse und ihre Gültigkeit im Adressregister. Ein Addierer bildet
zusätzlich Basis plus Offset und liefert den Übertrag für die nachfolgende
Bereichsprüfung.

`AddressUnit` wertet `ADDRESS_VALID` jetzt bei indirekten Zugriffen aus.
`VALID_IN` folgt Quellgültigkeit und Adressbereich. Die
[Gültigkeitsabnahme](../../docs/tiny_cpu_address_validity.md) dokumentiert die
frühere Lücke und ihre Regressionen.

## Memory

Speichert zu jeder Datenzelle sowohl einen 16-Bit-Wert als auch ein Gültigkeitsbit in
zwei parallelen RAMs. Schreibfreigabe und Takt übernehmen beide gemeinsam; beim Lesen
erscheinen Wert und Gültigkeit zusammen.

## ErrorFlags

Speichert die sechs Fehlerflags OVF, DIV0, ADDR, INV, ILL und INPUT. Ein gesetzter
Fehler bleibt über weitere Befehle erhalten; CLEAR_ERROR löscht die gespeicherten Fehler
beim entsprechenden Taktschritt.

## FetchDecode

Speichert den Programmzähler und liest damit das 22-Bit-Befehlswort aus dem ROM. Wählt
zwischen dem nächsten Befehl, einem Sprung und einem Interruptziel und erkennt das Ende
des zulässigen Programmbereichs.

## FetchDecodeControls

Übersetzt den sechs Bit breiten Opcode in die einzelnen Befehls-, Auswahl- und
Schreibsteuersignale. Die handgezeichnete Decoderstruktur bestimmt, welche Verarbeitung
für den aktuellen Befehl aktiv ist.

## IntegrationClock

Verteilt den eingehenden Takt auf Datenpfad, Adresspfad, Speicher, Fehlerflags und
Befehlssteuerung. Erzeugt selbst keinen neuen Takt und verändert dessen Frequenz nicht.

## IntegrationReset

Leitet RESET an den Reset-Eingang der Befehlssteuerung weiter. Setzt damit den
Befehlsablauf zurück; Daten-RAM, Akkumulator und Fehlerflags erhalten darüber keinen
allgemeinen Löschimpuls.

## AndArithmeticCircuit

Verknüpft die beiden Datenwörter bitweise mit UND. Gibt das Ergebnis für die aktivierte
Operation aus und meldet, ob die Eingänge ein gültiges Ergebnis erlauben.

## Operations

Wählt die angeforderte arithmetische oder bitweise Operation und deren Operanden aus.
Führt die Ergebnisse zu einem Ergebnisbus zusammen und liefert Gültigkeit, Aktivität,
Überlauf, Division durch null und ungültige Operanden.

## NotCircuit

Invertiert jedes Bit des Akkumulatorwerts. Die Operation übernimmt die Gültigkeit des
Akkumulators, wenn NOT aktiviert ist.

## MulArithmeticCircuit

Multipliziert zwei 16-Bit-Operanden und prüft, ob das vorzeichenbehaftete Ergebnis in
den vorgesehenen Datenbereich passt. Meldet Ergebnis, Gültigkeit und Überlauf.

## DivArithmeticCircuit

Dividiert den linken Operanden durch den rechten. Die Ergebnisfreigabe berücksichtigt
die Gültigkeit der Eingänge; eine aktivierte Division durch null wird gesondert
gemeldet.

## AddArithmeticCircuit

Addiert zwei 16-Bit-Operanden und prüft den vorzeichenbehafteten Überlauf. Liefert bei
aktivierter Addition das Ergebnis und die aus Eingangsgültigkeit und Bereichsprüfung
gebildete Ergebnisgültigkeit.

## SubArithmeticCircuit

Subtrahiert den rechten 16-Bit-Operanden vom linken und prüft den vorzeichenbehafteten
Überlauf. Liefert Ergebnis und Gültigkeit für die aktivierte Subtraktion.

## AddressRangeFBox

Entscheidet, ob eine erkannte Bereichsüberschreitung für den aktuellen Speicherbefehl
relevant ist. Verknüpft dazu die verwendete Adressierungsart mit Bereichs- und
Offsetfehlern.

## OrArithmeticCircuit

Verknüpft die beiden Datenwörter bitweise mit ODER. Aktivierung und Eingangsgültigkeit
bestimmen die Ergebnisfreigabe und das Gültigkeitssignal.

## XorArithmeticCircuit

Verknüpft die beiden Datenwörter bitweise mit exklusivem ODER: Ein Ergebnisbit ist
gesetzt, wenn die entsprechenden Eingangsbits verschieden sind. Liefert dazu die
Gültigkeit der aktivierten Operation.

## JumpBox

Prüft die gewählte Sprungart gegen Null-, Vorzeichen- und Fehlerstatus. Kombiniert
unbedingte und bedingte Sprünge zu den Steuersignalen für den Programmzähler.

## FetchUnit

Holt den aktuellen Befehl aus dem Programm-ROM und zerlegt ihn in Opcode und
unmittelbaren Operanden. Der Decoder erzeugt den gemeinsamen Steuerbus; Sprünge, Halt
und Interruptannahme beeinflussen den Befehlsablauf.

## AccumulatorUnit

Übernimmt Ergebniswert und Gültigkeit in den Akkumulator. Vier Auswahlstufen bestimmen
die Gültigkeit aus Speicherlesen, INVERT, INPUT oder ALU; rechts werden Wert und Status
wieder zu den oberen Ausgangspins geführt.

`CONTROL[19]`, `[20]` und `[21]` wählen Speicher-Gültigkeit für die drei Ladearten.
Die benötigten Steuerbits werden lokal aus dem Bus abgegriffen, nicht durch
Vergleiche des gesamten Buswerts mit ihren Bitnummern ausgewählt.
`[11]` wählt die bisherige Gültigkeit für INVERT, `[34]` die ungültige INPUT-Auswahl
und `[41]` die Schreibfreigabe. ALU_ACTIVE hat in der letzten Auswahlstufe Vorrang.

## AddressUnit

Bildet die tatsächlich verwendete Speicheradresse aus unmittelbarem Operanden,
Adressregister oder Adressregister plus Offset. Lädt das Adressregister bei Bedarf und
meldet Adressfehler nur für Befehle, die diese Adresse benutzen.

`AddressRegisterLoad` übernimmt normalerweise `IMMEDIATE_VALUE`; bei
`CONTROL[23]` (`LD_REG_ADR`) übernimmt er `READ_VALUE` samt `READ_VALID`.
`AddressAccess` sperrt ungültige indirekte Zugriffe und trennt INV von ADDR.
Die Verarbeitungskette und lokalen Steuerbus-Abgriffe sind im
[aktuellen Prüfbericht](../../docs/tiny_cpu_address_validity.md) erläutert.

## AddressRegisterLoad

Wählt Registerladewert und Ladefreigabe, prüft den Bereich 0..4095 und bei
Speicherladen die Quellgültigkeit. Ungültige Ladeversuche liefern 0 INVALID
und getrennte Fehleranforderungen für Konstanten und gelesene Werte.

## AddressAccess

Verknüpft Bereichsprüfung, verwendete Adressierungsart und Registergültigkeit
zur Zugriffsfreigabe. Direkte Zugriffe hängen nicht vom unbenutzten Register
ab. Ungültige Register setzen INV; Bereichsfehler gültiger Adressen setzen ADDR.

## MemoryUnit

Verbindet den internen Datenspeicher mit dem optionalen externen Speicherpfad. Wählt den
gelesenen Wert samt Gültigkeit oder den unmittelbaren Operanden aus und steuert
Schreibzugriffe mit Akkumulatorwert und Gültigkeitsbit.

## ExecutionUnit

Bündelt Operanden und Gültigkeitssignale und reicht sie an die Rechen- und Logikeinheit
weiter. Liefert Ergebnis, Ergebnisgültigkeit, Aktivität sowie die zugehörigen
Fehleranzeigen.

## FaultUnit

Sammelt Fehler aus Rechnung, Adressbildung und ungültigen Werten, etwa beim Laden oder
Ausgeben. Übergibt die Setzanforderungen an die gespeicherten Fehlerflags und
berücksichtigt auch eine unzulässige Interrupt-Rückkehr.

## BranchUnit

Fasst Fehler- und Ergebnisflags zusammen und verbindet sie mit der dekodierten
Sprungbedingung. Daraus entstehen die Signale, mit denen die Befehlssteuerung einen
Sprung ausführt oder beim nächsten Befehl bleibt.

## CoreDiagnostics

Zeigt ausgewählte interne Signale wie Programmzähler, Sprungzustand und Steuerbits an.
Die Probes beobachten die Schaltung, ohne ihren Ablauf zu steuern; einzelne Anzeigenamen
stammen aus älteren Entwicklungsständen.

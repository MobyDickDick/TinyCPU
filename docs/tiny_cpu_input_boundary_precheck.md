# AP 22.1: Eingangskontrolle vor der Eingabegrenze

**Historischer Zwischenstand vom 6. November 2026:** Schritt 2 des
[Eingabeplans](tiny_cpu_input_plan.md) wurde vor der Implementierung gestoppt.
Die damalige erneute Baseline scheiterte an einem undefinierten
öffentlichen `ERROR_INPUT`. Die zusätzliche Eingabegrenze und ihre beiden
Boxvarianten sind weiterhin nicht implementiert.

**Späterer Stand desselben Tages:** Der Benutzer hat anschließend die
Korrektur sämtlicher Schaltungen beauftragt. Die hier eingegrenzte Lücke ist
nun in der produktiven FaultUnit geschlossen. Die ursprünglichen Befunde
und der damalige Stop bleiben nachfolgend als Verlauf erhalten. Aktuelle
Abnahme und weitere Reparaturen: [projektweiter Bericht](tiny_cpu_circuit_repair_20261106.md).

## Ausgangsstand und Stop-Regel

Geprüft wurde Commit `2bc3101` einschließlich der bereits vorhandenen lokalen
AddressUnit-Verschiebung. Die eingehende Quelldatei ist unter
`artifacts/ap22-input-boundary-20261106/TinyCPU-before.circ` gesichert;
ihr SHA-256 lautet
`bcf09366670562ef35aa6a194d64f0941b11e6e1b2a54cc76cf8d84a5cc8def2`.

Der Eingabeplan schreibt vor: „Beim ersten elektrischen Unterschied wird
gestoppt.“ Deshalb wurden nach dem Befund keine Eingabevarianten ergänzt,
keine Anforderungen gelockert und keine vollständigen Matrizen geöffnet.
Die erfolgreiche passive Baseline vom 5. November bleibt ein historischer
Nachweis für ihren damaligen Ausgangsstand `0781124`.

## Erster Unterschied und passive Eingrenzung

`scripts/diagnose-logisim-input-baseline.py` führt unverändert
`LOAD_CONST(7); INPUT(); HALT()` mit leerer VM-Eingabequelle aus. Schon an
Flanke 1, `pre`, lehnt der vollständige Kern-Comparator `ERROR_INPUT=U` ab.
Die Rohdaten erreichen zwar den Normalhalt; dieser ersetzt den abgebrochenen
Zustandsvergleich nicht.

Ein zusätzlicher rein passiver Lauf derselben ROM-Kopie liest die benannten
Pfade `FAULT_UNIT/ERROR_FLAGS/SET_INPUT` und
`FAULT_UNIT/ERROR_FLAGS/INPUT_OUT` neben dem öffentlichen `ERROR_INPUT`:

| Messung | SET_INPUT | INPUT_OUT | ERROR_INPUT |
| --- | --- | --- | --- |
| Flanke 1 pre | 0 | 0 | U |
| Flanke 1 post / Flanke 2 pre | 1 | 0 | U |
| Flanke 2 post / Flanke 3 pre/post | 0 | 1 | U |

Der interne Sticky-Zustand wird also korrekt gesetzt, erreicht aber den
öffentlichen Ausgang nicht. Die positionsunabhängige Netzprüfung bestätigt:
Der Ausgang `ErrorFlags.INPUT_OUT` ist innerhalb von `FaultUnit` nicht mit
dem Blattpin `INPUT` verbunden. Dieser Pin steht bei `(1610,290)`, die
Rückführung endet dagegen erst auf der Strecke `(1620,290)` bis `(1640,290)`.
Es fehlt die zehn Pixel lange Verbindung zum Pin. Die Symbolbindung verweist
korrekt auf den vorhandenen Pin; der Befund liegt innerhalb der Fehlerbox.

## Abgegrenzter Reparaturkandidat in einer Artefaktkopie

Ausschließlich in `artifacts/ap22-input-boundary-20261106/candidate/TinyCPU.circ`
wurde eine einzige Leitung geändert:

```diff
-    <wire from="(1620,290)" to="(1640,290)"/>
+    <wire from="(1610,290)" to="(1640,290)"/>
```

Damit besteht die Netzprüfung. Der vollständige elektrische Kern-/VM-Vergleich
für dasselbe Dreierprogramm besteht anschließend mit drei Flanken und sechs
Beobachtungen einschließlich sämtlicher bisheriger Zustands- und RAM-Felder.
Die produktive Quelldatei blieb nach Bytevergleich unverändert. Es wurde
keine Reparatur in die Quelle übernommen, keine Zeichnung umgeordnet und
keine native Sichtabnahme behauptet.

## Reproduktion und Nachweise

Verwendet wurden die vorhandene Logisim-evolution-JAR 4.1.0, OpenJDK 27 und
Python 3.14.5; ein Download war nicht nötig. PowerShell:

```powershell
$env:PYTHONPATH='src'
$env:JAVA='C:/Program Files/jdk-27/bin/java.exe'
$env:LOGISIM_JAR=(Resolve-Path .venv/Include/logisim-evolution-4.1.0-all.jar).Path
$env:JAVA_TOOL_OPTIONS='-Djava.util.prefs.PreferencesFactory=LocalPreferencesFactory -Xbootclasspath/a:C:/Users/marku/myCloud/TinyCPU/artifacts/address-validity-20261104/prefs'
python scripts/diagnose-logisim-input-baseline.py --output artifacts/ap22-input-boundary-20261106/before
```

Der erwartete Abbruch erzeugt `before/baseline/diagnostic.json`; ROM-Kopie,
Stimuli, Sollzustände, Aufruf, stderr und unveränderte TSV-Rohdaten bleiben
ebenfalls erhalten. Die ergänzende lokale Diagnose lässt sich anschließend
mit `python artifacts/ap22-input-boundary-20261106/diagnose.py` wiederholen.
Sie speichert `fault.tsv`, `fault-probes.tsv`, `fault-command.json`,
`fault-stderr.txt`, `diagnosis.json` sowie die Vergleichsartefakte unter
`candidate-baseline/` und `candidate-baseline.tsv`.

## Nächster begrenzter Schritt

Zuerst ausschließlich die belegte Ausgangslücke von `FaultUnit.INPUT`
reparieren und den Anschluss durch einen benannten, positionsunabhängigen
Regressionstest absichern. Die ursprüngliche Fehlerkopie muss weiterhin an
Flanke 1 pre bei `ERROR_INPUT` abgelehnt werden. Danach die passive
INPUT-Baseline einschließlich interner Messpfade erneut abnehmen. Erst auf
dieser wiederhergestellten Grundlage Schritt 2 des Eingabeplans fortsetzen.
Andere Layoutbefunde und die vollständige Eingabeabnahme bleiben getrennt offen.

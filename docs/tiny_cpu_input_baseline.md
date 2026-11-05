# AP 22.1: Passive INPUT-Baseline

**Stand: 5. November 2026. Status:** Schritt 1 des
[Eingabeplans](tiny_cpu_input_plan.md#umsetzung-in-einzeln-prüfbaren-schritten)
ist abgeschlossen. Gemessen wurde Commit `0781124` mit
`LOAD_CONST(7); INPUT(); HALT()` am bisherigen `TinyCPUMain`.
Die elektrische Implementierung gültiger externer Eingaben bleibt offen.

## Umfang und Ergebnis

Der neue Treiber `scripts/diagnose-logisim-input-baseline.py` führt zuerst
den vollständigen bestehenden Kern-/VM-Vergleich aus und wiederholt denselben
ROM-Lauf mit zusätzlichen benannten internen Messpunkten. Auch im zweiten Lauf
bleibt der vollständige Zustands-/RAM-Vergleich aktiv. Die VM verwendet eine
leere Eingabequeue. Es werden weder öffentliche Pins noch Beobachtungsbauteile
eingefügt; nur die ROM-Inhalte einer Artefaktkopie werden ersetzt.
Alle produktiven `.circ`-Dateien bleiben nach Bytevergleich unverändert,
einschließlich beider geschützter Decoderzeichnungen.

Beide elektrischen Läufe bestehen mit jeweils drei steigenden Flanken und
sechs vollständig propagierten Beobachtungen. Es gibt keine E/U-Werte,
Oszillation oder Zeitüberschreitung. Das Adressregister und der gesamte RAM
bleiben unverändert; Normalhalt wird erreicht.

| Messpunkt | Flanke 1 pre: LOAD_CONST | Flanke 1 post / Flanke 2 pre: INPUT liegt an | Flanke 2 post: INPUT übernommen |
| --- | --- | --- | --- |
| PC | 0 | 1 | 2 |
| ACC / ACC_VALID | 0 / 0 | 7 / 1 | 0 / 0 |
| Decoder INPUT | 0 | 1 | 0 |
| Decoder ACC_WRITE_REQUEST | 1 | 1 | 0 |
| Datapath.DATA_IN | 7 | 0 | 0 |
| Datapath.ACC_LOAD | 1 | 1 | 0 |
| Datapath.VALID_IN | 1 | 0 | 1 |
| ErrorFlags.SET_INPUT | 0 | 1 | 0 |
| ErrorFlags.INPUT_OUT / ERROR_INPUT | 0 / 0 | 0 / 0 | 1 / 1 |
| Alle übrigen Sticky-Flags | 0 | 0 | 0 |

`DATAPATH_CLK` ist bei jedem `pre` 0 und bei jedem `post` 1. Die
nach Flanke 1 sichtbare INPUT-Anforderung gehört zur erst folgenden Flanke 2.
Die nach Flanke 2 wieder anliegende Ladegültigkeit 1 gehört zum inaktiven
HALT-Datenpfad: `ACC_LOAD=0` hält den gespeicherten ungültigen Akkumulator.
Das INPUT-Flag bleibt bis einschließlich Flanke 3 post gesetzt.

## Benannte Wege für den folgenden Umbau

- **Befehl und Laden:** `FETCH_UNIT/FETCH_DECODE_CONTROLS/INPUT`
  stimmt mit Bit 34 der beiden Eingänge `ACCUMULATOR_UNIT/CONTROL` und
  `FAULT_UNIT/CONTROL` überein.
  `FETCH_UNIT/FETCH_DECODE_CONTROLS/ACC_WRITE_REQUEST` erreicht
  `ACCUMULATOR_UNIT/DATAPATH_INSTANCE/ACC_LOAD` mit Wert 1.
- **Daten:** `ACCUMULATOR_UNIT/RESULT_VALUE` führt den bisherigen Ergebnisweg
  zum `DATAPATH_INSTANCE/DATA_IN`. Bei INPUT wird elektrisch die Null
  gemessen. Die Eingabevariante muss hier den angebotenen Wert auswählen
  und bei ungültigem Angebot weiterhin die kanonische Null laden.
- **Gültigkeit:** Der Abgriff von CONTROL-Bit 34 wählt innerhalb der
  `AccumulatorUnit` die bestehende feste Null als Ladegültigkeit.
  Elektrisch liegt am benannten `DATAPATH_INSTANCE/VALID_IN` vor Flanke 2
  tatsächlich 0 an. Die Eingabevariante muss stattdessen die externe
  Eingabegültigkeit auswählen.
- **Fehler:** Der INPUT-Abgriff in `FaultUnit` erreicht
  `FAULT_UNIT/ERROR_FLAGS/SET_INPUT`. Vor Flanke 2 ist dieser Eingang 1,
  danach sind `INPUT_OUT` und der öffentliche `ERROR_INPUT` 1.
  Die Eingabevariante muss diese Ursache auf einen fehlgeschlagenen INPUT
  begrenzen; andere Fehlerursachen und die Sticky-Speicherung bleiben erhalten.

`FETCH_UNIT/FETCH_DECODE_CONTROLS/SET_INPUT` ist ein anderer Ausgang:
Er bezeichnet den ausdrücklichen Fehler-Setzbefehl und bleibt in diesem
Programm durchgehend 0. Er ist nicht die Quelle des hier gemessenen
INPUT-Fehlers. Eine anfängliche Gleichheitsannahme im Beobachter wurde deshalb
korrigiert; dessen Abbruchdiagnose bleibt als
`observer-assumption-diagnostic.json` erhalten. Es wurde keine Leitung repariert.

Der bestätigte Fehlerfall belegt keine defekte Leitung. Die zusätzliche Grenze
`TinyCPUInputMain` mit `AccumulatorInputUnit` und `FaultInputUnit` ist als
Schritt 2 des Eingabeplans umzusetzen. Dabei gelten die bestehenden
Schnittstellenverträge und die dort geforderte native Sichtprüfung.

## Reproduktion und Nachweise

Die lokalen Nachweise liegen unter `artifacts/ap22-input-baseline-20261105/`:

- `baseline.tsv`, `baseline/expected.json`, `baseline/inputs.json`,
  `baseline/probes.tsv`, `baseline/command.json`, `baseline/TinyCPU.circ`
  und `baseline/stderr.txt`: unveränderte Rohdaten und vollständiger Kernlauf.
- `internal.tsv`, `internal-probes.tsv`, `internal-command.json` und
  `internal-stderr.txt`: zusätzlicher passiver Lauf derselben Projektkopie.
- `proof.json`: überprüfte interne Beobachtungen, Bytegleichheit der
  Quellschaltungen und SHA-256 von Kernquelle und Simulator-JAR.
- `comparator-controls.json`: fünf abgelehnte Verfälschungen der gespeicherten
  Messdaten (falscher INPUT-Datenwert, E-Gültigkeit, falsche Busbreite,
  falscher ACC-Zustand, fehlende Beobachtung). Dies sind Parser-/Vergleichs-
  kontrollen, keine elektrischen Fehlerkopien der künftigen Eingabeimplementierung.
- `core-trace-tests.txt` und `vm-tests.txt`: 14 Kerntrace- und sechs VM-Tests,
  alle bestanden, jeweils Exit 0.

Verwendet wurden Python 3.14.5, OpenJDK 27 und die vorhandene gepinnte
Logisim-evolution-JAR 4.1.0; ein Download war nicht nötig. PowerShell:

```powershell
$env:PYTHONPATH='src'
$env:JAVA='C:/Program Files/jdk-27/bin/java.exe'
$env:LOGISIM_JAR=(Resolve-Path .venv/Include/logisim-evolution-4.1.0-all.jar).Path
$env:JAVA_TOOL_OPTIONS='-Djava.util.prefs.PreferencesFactory=LocalPreferencesFactory -Xbootclasspath/a:C:/Users/marku/myCloud/TinyCPU/artifacts/address-validity-20261104/prefs'
python scripts/diagnose-logisim-input-baseline.py --output artifacts/ap22-input-baseline-20261105
New-Item -ItemType Directory -Force artifacts/ap22-input-baseline-20261105/tmp | Out-Null
$env:TEMP=(Resolve-Path artifacts/ap22-input-baseline-20261105/tmp).Path
$env:TMP=$env:TEMP
python -m unittest discover -s tests -p test_tiny_cpu_core_trace.py -v
python -m unittest discover -s tests -p test_tiny_cpu_vm.py -v
```

Die Preferences-Hilfsklassen stammen aus der vorigen lokalen Abnahme.
Beim ersten Unit-Aufruf ohne das lokale TEMP-Verzeichnis scheiterten drei
Dateisystemtests an den Sandbox-Rechten im Windows-Tempverzeichnis. Mit dem
obigen TEMP-Pfad bestehen alle 20 Tests ohne Codeänderung.

Gemäß Paketgrenze wurden keine vollständigen Kern-/Systemmatrizen wiederholt
und keine Schaltungen geändert. Die bekannten Offline-Rasterbefunde werden
dadurch nicht geschlossen. Dieser Nachweis ist weder die vollständige
AP-22.1-Eingabeabnahme noch eine GUI- oder Release-Abnahme.

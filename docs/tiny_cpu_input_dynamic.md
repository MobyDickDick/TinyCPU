# AP 22.1: Dynamische INPUT-Stimuli und Abnahme

**Aktueller Nachtrag vom 10. November 2026:** Der unten festgehaltene
Reset-Befund ist [lokal korrigiert](tiny_cpu_input_reset_repair.md). Alle 23
dynamischen Fälle, die drei elektrischen Fehlerkopien und alle 63 bestehenden
Kernfixtures über das Eingabetop mit inaktiver Eingabe bestehen. Der neue
Treiber ist verpflichtend in `scripts/test-logisim.sh` eingebunden. Die
Schritte 3 und 4 und damit AP 22.1 sind abgeschlossen; Baseline-, System- und
Operator-Gates bestehen weiter.
Die folgenden Abschnitte dokumentieren den vorherigen Stop einschließlich
seiner unveränderten Rohdaten; die aktuelle Korrektur und Abnahme stehen im
verlinkten Folgebericht.

**Historischer Zwischenstand vor der Korrektur, 10. November 2026.** Schritt 3 des
[Eingabeplans](tiny_cpu_input_plan.md) ist implementiert, aber noch nicht
vollständig elektrisch abgenommen. 19 dynamische Fälle bestehen; der letzte
Fall `reset` scheitert an Flanke 1, `post`, bei `ACC`: Soll 0, Ist 23.
Die dokumentierte Stop-Regel wurde angewendet. Die drei anschließenden
elektrischen Fehlerkopien wurden nicht geöffnet. Schritt 4 und die
INPUT-Checkbox in AP 22.1 bleiben offen.

Ausgangscommit: `02b058ce5bafaabe166e9ccbaa12bb830664d661`, ergänzt um die hier
beschriebenen Treiber-, Test- und Dokumentationsänderungen. Alle 24 produktiven
`.circ`-Dateien sind bytegleich zu diesem Commit, einschließlich beider
geschützter Decoder. Der SHA-256 von `TinyCPU.circ` ist
`f38b1d1c6e17bb5f8658bcedffc2f03897dc1f80811e5e981e4a86ad7abc54b9`.

## Implementierter Vertrag

`hardware/logisim/tinycpu_input_cases.json` enthält 20 feste Fälle mit
Assemblerprogramm, flankenbezogenen Angeboten, unabhängig festgelegten
Zustandserwartungen und erwarteten Verbrauchsereignissen.
`scripts/test-logisim-input.py` führt sie seriell aus. Jede Fixture behält den
vollständigen Kern-/VM-Vergleich einschließlich aller Flags, Ausgaben und RAM.
Ein Fehler beendet die Matrix vor weiteren Fällen und Mutationen.

`inputs.json` verwendet das Schema `tinycpu-input-stimuli-v1` mit genau den
Feldern `schema` und `edges`. Jede Zeile enthält:

| Feld | Vertrag |
| --- | --- |
| `edge` | Lückenlose Flankennummer, beginnend bei 1 |
| `reset` | Ganzzahl 0 oder 1 |
| `value` | Definiertes 16-Bit-Muster als Ganzzahl 0 bis 65535 |
| `valid` | Ganzzahl 0 oder 1 |
| `source` | `host`, `invalid`, `empty` oder `idle` |
| `entry` | Stabile Eintragskennung bei vorhandener Quelle; sonst `null` |
| `host_value` | Nur bei `host` erforderlich: ursprüngliche Ganzzahl vor der Busabbildung |

Hostwerte außerhalb −32768 bis 32767 müssen `valid=0` erhalten. Der
Referenzadapter prüft den ursprünglichen Hostwert zusätzlich gegen die VM;
ein gültiges Busmuster wird vorzeichenrichtig dekodiert. Leere und ausdrücklich
ungültige Quellen bleiben im Protokoll unterscheidbar. Unbekannte, doppelte
oder fehlende Felder, vertauschte Zeilen und falsche Breiten werden abgelehnt.
Fehlende oder zusätzliche Angebote gegenüber der ausgeführten Instruktionsfolge
sind ebenfalls Fehler. JSON-Bools zählen nicht als Ganzzahlen.

Der Java-Exporter erhält mit `--inputs STIMULI LEDGER` ausschließlich die
Spalten `edge`, `RESET`, `INPUT_VALUE` und `INPUT_VALID`, ohne VM-Sollzustände
oder erwartete Verbrauchsereignisse. Er legt die Werte bei niedrigem Takt vor
`pre` an und hält sie durch die steigende Flanke bis einschließlich `post`.
Die zusätzliche Tracevariante beobachtet `INPUT_VALUE[16]`, `INPUT_VALID`,
`INPUT_CONSUME` und `RESET`; die bisherigen Spalten bleiben enthalten.
Das bisherige Traceformat ohne Eingabeoption bleibt kompatibel.

`consumption.tsv` liest dieselben öffentlichen Pins unabhängig von der
Probeliste direkt vor jeder physischen Flanke. Das separate Quellenprotokoll
vergleicht die tatsächlichen Leseversuche mit der festen Ereignisliste und
zählt entfernte Einträge. Ein leerer Leseversuch entfernt keinen Eintrag;
ein vorhandener ungültiger Eintrag wird entfernt. Doppelte oder ausgelassene
Transaktionen und Verbrauch bei Reset oder Nicht-INPUT werden abgelehnt.
Auch Angebote ohne Verbrauch erscheinen in der Rohdatei.

## Elektrischer Befund

Die ersten 19 Fälle bestehen vollständig:

- Gültige Eingaben 0, −1, −32768, 32767 und 23 samt PRINT.
- Leere Quelle nach ACC=7; ungültige Muster 0, `0x8000`, `0xffff`;
  Hostwerte −32769 und 32768.
- Zwei direkte INPUTs mit verschiedenen Werten; INPUT/PRINT/INPUT mit
  später leerer Quelle und getrennten Versuchs-/Entnahmezahlen.
- Erholung durch gültiges INPUT bei sticky INPUT-Flag; CLEAR_ERROR bei
  weiterhin ungültigem ACC; ungültiger PRINT mit eigener INV-Ursache.
- INPUT=−32768 über RAM-Zelle 101 bis LOAD und PRINT.
- Wechselnde Angebote ohne INPUT sowie ein übersprungener INPUT.

Der letzte Fall hält das gültige Angebot 23 über zwei Reset-Flanken und
führt danach `INPUT; PRINT; HALT` aus. Bereits die erste Flanke weicht ab:

| Beobachtung | RESET | INPUT_CONSUME | ACC | ACC_VALID |
| --- | --- | --- | --- | --- |
| Flanke 1 pre, gemessen | 1 | 0 | 0 | 0 |
| Flanke 1 post, erwartet | 1 | 0 | 0 | 0 |
| Flanke 1 post, gemessen | 1 | 0 | 23 | 1 |

Der Verbrauchsexport sperrt korrekt; der Akkumulator übernimmt trotzdem das
Angebot. Damit verändert ein Angebot den Zustand außerhalb einer
INPUT-Transaktion. Die späteren Zeilen derselben Exportdatei sind gesicherte
Rohdaten, keine nach dem ersten Unterschied bestandenen Vergleichsschritte.

Der bestehende CPU-Reset setzt nur den Befehlsablauf zurück; er löscht
Akkumulator, Adressregister, RAM und Sticky-Flags nicht allgemein.
Der neue Referenzadapter erhält diese Zustände während Reset und führt keine
INPUT-Transaktion aus. Er verwendet dafür ausdrücklich nicht `TinyCPU.reset()`,
das einen umfassenderen Software-Reset beschreibt. Ein zusätzlicher Unit-Test
schützt dieses Halten auch bei einem bereits gültigen Akkumulator.
Eine allgemeine Löschung dieser Register wäre keine zulässige Behebung des
hier beobachteten Eingabeproblems.

## Prüfstand und Reproduktion

Umgebung: Windows, Python 3.14.5, OpenJDK 27+35-2325 und die bereits vorhandene
Logisim-evolution-JAR 4.1.0. Es gab keinen Download. PowerShell im Repository:

```powershell
New-Item -ItemType Directory -Force artifacts/ap22-input-dynamic-20261110/tmp | Out-Null
$env:PYTHONPATH='src'
$env:JAVA='C:/Program Files/jdk-27/bin/java.exe'
$env:LOGISIM_JAR=(Resolve-Path .venv/Include/logisim-evolution-4.1.0-all.jar).Path
$env:TEMP=(Resolve-Path artifacts/ap22-input-dynamic-20261110/tmp).Path
$env:TMP=$env:TEMP
$env:JAVA_TOOL_OPTIONS='-Djava.util.prefs.PreferencesFactory=LocalPreferencesFactory -Xbootclasspath/a:C:/Users/marku/myCloud/TinyCPU/artifacts/address-validity-20261104/prefs'
python scripts/test-logisim-input.py --output artifacts/ap22-input-dynamic-20261110/reproduce
```

Der letzte Aufruf endet aktuell absichtlich mit Exit 1 am beschriebenen ersten
Unterschied. Die Preferences-Hilfsklasse stammt aus der vorhandenen lokalen
Abnahme und umgeht nur das hier nicht beschreibbare Windows-Preferences-
Verzeichnis; normale Simulatorinstallationen benötigen diese Einstellung nicht.

Nachweise unter `artifacts/ap22-input-dynamic-20261110/`:

| Prüfung | Ergebnis und Artefakt |
| --- | --- |
| Dynamische elektrische Matrix | 19 bestanden, Stop bei `reset`; unveränderte Rohdaten, Programme, Angebote, Erwartungen, exakte Befehle und stderr unter `first/` |
| Erneuter Vergleich der erhaltenen Rohdaten mit dem fertigen Comparator | Derselbe erste Unterschied; `result.json`, einschließlich Quellhashes und Bytevergleich aller Schaltungen gegen HEAD |
| Offline-Verifikator | Exit 0; `verify.txt` |
| Schaltungsstruktur | Exit 0; `structure.txt` |
| Java-Stimulusparser | Sechs fehlerhafte Verträge vor dem Öffnen einer Schaltung abgelehnt: fehlende/zusätzliche Zeilen, Reihenfolge, undefinierte Bits, Breite und Spalten; `parser/results.json` |
| Windows-Unit-Suite | 291 Tests, Exit 1; alle 13 neuen Vertragstests bestehen, sieben vorhandene Layout-Subtestfehler; `unit-final.txt` |
| Kontrolllauf aus unverändertem HEAD-Archiv | Dieselben sieben Layout-Subtestfehler in zwei unveränderten Testmethoden; `layout-head.txt` und `head-layout-baseline/` |

Die Layoutfehler betreffen `TinyCPUMain`, `EffectiveAddress`, `AddressPath`,
`FetchDecode`, `Operations` und `MulArithmeticCircuit`; `TinyCPUMain` erscheint
in beiden Testmethoden. Sie wurden nicht durch eine Anpassung der Zeichnungen,
Referenzen oder Anforderungen unterdrückt. Der vollständige Offline-Testlauf
ist deshalb trotz bestandenem Verifikator und Strukturprüfung nicht grün.

Bei neuen Läufen bewahrt `run-summary.json` auch den abgebrochenen Teilstand.
`proof.json` wird ausschließlich nach vollständig bestandener Matrix und allen
drei elektrischen Negativkontrollen erzeugt; für diesen Teilstand existiert
kein solcher Abschlussnachweis. System-, Operator- und vollständige elektrische
Baseline-Gates wurden nach dem INPUT-Unterschied nicht erneut geöffnet.

## Nächster begrenzter Schritt

Nur den Reset-Fall um seine erste steigende Flanke passiv weiterverfolgen:
`AccumulatorInputUnit.RESET`, `CONTROL.34`, `INPUT_CONSUME_REQUEST` sowie
`DATAPATH_INSTANCE.ACC_LOAD`, `DATA_IN`, `VALID_IN` und
`DATAPATH_STARTUP_RESET` über benannte Pfade vergleichen. Erst aus dem
benannten ersten internen Unterschied eine lokale Sperre der INPUT-Übernahme
während Reset ableiten. Die Bestands-Resetsemantik und beide geschützten
Decoder erhalten.

Danach zuerst diesen Reset-Fall erneut abnehmen, anschließend die dynamische
Matrix und die drei vorgesehenen elektrischen Fehlerkopien ausführen.
Erst bei deren Erfolg ist Schritt 3 abgeschlossen. Schritt 4 bindet danach
den Treiber verpflichtend in `scripts/test-logisim.sh` ein und prüft die
bestehenden Kernfixtures zusätzlich über das Eingabetop.

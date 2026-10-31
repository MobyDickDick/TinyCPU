# Topologische Nachprüfung von TinyCPUMain

## Prüfung des Neuzeichnungsstands `0089e68`

Die erneute Anschlussprüfung der kompakteren Übersicht findet drei offene
öffentliche Ausgänge: `PRINT_ENABLE`, `PRINT_ADDRESS_ENABLE` und `HALTED`.
Die zugehörigen Leitungen von `FetchUnit.PRINT`, `FetchUnit.PRINT_ADDR` und
`FetchUnit.HALT` endeten noch rechts neben den versetzten Ausgangspins und
jeweils eine Rasterzeile oberhalb des Anschlusses. Der bestehende benannte
Porttest schlug vor der Korrektur für alle drei Signale fehl
(`artifacts/wiring-review-0089e68/hierarchy-before.txt`).

Die drei waagerechten Leitungen enden jetzt kurz vor den Ausgangspins und
erreichen diese über je einen kurzen Knick. Die freien Rasterzeilen zwischen
den langen Leitungen und die aktuelle Pinanordnung bleiben erhalten. Alle
41 Komponenten einschließlich ihrer Positionen und Attribute sowie sämtliche
Teilkreisdefinitionen sind unverändert. Die Übersicht enthält durch die sechs
kurzen Anschlusssegmente 285 statt 279 Leitungssegmente.

Alle benannten Portnetze stimmen danach vollständig mit Referenz `6ab7c89`
überein. Weitere fehlerhafte Verbindungen wurden nicht gefunden. Der
unveränderte freigegebene Topologie-Fingerabdruck wird wieder erreicht:
`0d7893c6fbc0869006a4bd8ffa96313c405fac87719787ca1e71a3348159f980`.
Der Nachweis liegt unter `artifacts/wiring-review-0089e68/topology-proof.json`;
der Logisim-Zeichenexport `after.png` wurde gesichtet.

Offline-Verifier, statischer Leitungstest, alle 212 Python-Tests und Logisims
Prüfung auf elektrische Fehlerwerte für Kern und Peripherie bestehen
(`verify.txt`, `structure.txt`, `unit-after.txt`, `electrical.txt` im selben
Nachweisverzeichnis).

Auch Countdown und alle 61 elektrischen Kernfixtures, die sieben
Peripheriefälle, der STEP-Takttest sowie die Kern-, STORE-, PRINT-, Immediate-,
Decoder- und Registerpfadprüfungen einschließlich ihrer Negativkontrollen
bestehen (`core.txt`, `system.txt`, `operator.txt`, `core-mutation.txt`,
`store.txt`, `print.txt`, `immediate.txt`, `decode.txt`, `address-register.txt`).

## Erneute Prüfung des Neuzeichnungsstands `1648040`

Am 31. Oktober 2026 wurde die anschließend erneut gezeichnete Übersicht
vollständig anhand ihrer benannten Anschlüsse geprüft. Drei Leitungswege
wichen von der freigegebenen elektrischen Struktur ab:

| Signal | Fehler im Neuzeichnungsstand | Korrektur |
|---|---|---|
| `FetchUnit.HALT` | Mit `FaultUnit.ADDR` verbunden; `HALTED` offen | Eigenständige Leitung zu `HALTED` |
| `FetchUnit.PRINT_ADDR` | Mit `FaultUnit.INV` verbunden; `PRINT_ADDRESS_ENABLE` offen | Eigenständige Leitung zu `PRINT_ADDRESS_ENABLE` |
| `BranchUnit.OVF` | Mit dem INPUT-Fehlernetz verbunden | Rückführung vom OVF-Fehlernetz |

Es wurden ausschließlich diese Leitungswege angepasst. Alle 41 Komponenten
einschließlich Positionen und Attribute bleiben erhalten. Die Übersicht hat
286 statt 288 Leitungssegmente. Sämtliche nachfolgenden Teilkreisdefinitionen,
einschließlich `FetchDecodeControls`, sind bytegenau unverändert.

Der vollständige Vergleich aller benannten Portnetze mit Referenz `f7bdc87`
stimmt überein. Auch der unveränderte Referenz-Fingerabdruck
`0d7893c6fbc0869006a4bd8ffa96313c405fac87719787ca1e71a3348159f980`
wird wieder erreicht. Die bestehende Regression prüft zusätzlich die getrennten
HALT-, PRINT- und PRINT_ADDRESS-Netze sowie deren öffentliche Ausgänge; sie
schlug vor der Schaltungskorrektur fehl und besteht danach.

Nachweise liegen lokal unter `artifacts/wiring-review-repeat/`:

- Offline-Verifier und statischer Leitungstest über alle Projektdateien bestanden.
- Alle 212 Python-Tests bestanden (`unit-after.txt`).
- Logisim meldet definierte elektrische Ausgänge für Kern und Peripherie (`electrical.txt`).
- Countdown und alle 61 elektrischen Kernfixtures bestanden (`core.txt`).
- Kern-, STORE-, PRINT-, Immediate-, Decoder- und Registerpfadprüfungen
  einschließlich aller vorgesehenen Negativkontrollen bestanden
  (`core-mutation.txt`, `store.txt`, `print.txt`, `immediate.txt`, `decode.txt`,
  `address-register.txt`).
- Alle sieben Peripheriefälle sowie der STEP-Takttest bestanden
  (`system.txt`, `operator.txt`).
- Komponenten-, Teilkreis- und Anschlussvergleich: `topology-proof.json`;
  gesichteter Logisim-Zeichenexport: `after.png`.

## Vorherige Prüfung des Neuzeichnungsstands `171d99f`

Am 31. Oktober 2026 wurde der manuell neu gezeichnete Stand `171d99f`
(im Ausgangscheckout `d760452`) anhand benannter Bauteilanschlüsse geprüft.
Die aktuelle Anordnung bleibt erhalten; es wurde kein älteres Layout
zurückgeschrieben.

## Befund und Korrektur

| Anschluss | Vorher tatsächlich verbunden | Korrigierte Verbindung |
|---|---|---|
| `BranchUnit.DIV0` | `FaultUnit.ILL` | `FaultUnit.DIV0` |
| `BranchUnit.ILL` | `FaultUnit.DIV0` | `FaultUnit.ILL` |
| `BranchUnit.OVF` | Adressfehlernetz, gemeinsam mit `BranchUnit.ADDR` | `FaultUnit.OVF` |
| `BranchUnit.INV` | `FetchUnit.ERROR_HALT` | `FaultUnit.INV` |
| Öffentlicher Pin `HALTED_WITH_ERROR` | offen; die Leitung endete daneben | `FetchUnit.ERROR_HALT` |

Die bestehenden Leitungskorridore wurden gezielt angepasst. Die Abzweige
für OVF und INV enden jetzt an ihren eigenen Fehlernetzen; die vorherigen
Verbindungspunkte auf den fremden Netzen sind entfernt. DIV0 und ILL erreichen
die richtigen benannten Eingänge. Der Fehlerhalt erreicht seinen öffentlichen
Ausgang. Der INV-Verlauf verwendet eine freie Nachbarspur, damit er nicht mit
dem Adressbus zusammenfällt.

Alle 41 Komponenten einschließlich ihrer Positionen und Attribute bleiben
unverändert. Die Übersicht enthält nun 299 statt 301 Leitungssegmente.
Sämtliche Teilkreisdefinitionen hinter `TinyCPUMain`, insbesondere der
geschützte Decoder, sind gegenüber dem Ausgangscheckout bytegenau unverändert.

## Prüfung nach einem Speichern mit Logisim

Der bisherige Offline-Prüfer interpretierte ausgelassene Splitter-Bitwerte
als Null und verlangte ein `label`, das Logisim für Splitter nicht speichert.
Er berücksichtigte außerdem XML-Komponentenreihenfolge und nicht gespeicherte
Standardattribute im Topologie-Fingerabdruck. Diese Darstellungsdetails
führten nach dem Speichern zu falschen Befunden.

Die Analyse verwendet jetzt Logisims tatsächliche Standard-Bitverteilung,
findet den Steuerbus-Splitter anhand seiner Schnittstelle und ordnet
Teilkreisports stabil nach ihren Namen. Der Fingerabdruck normalisiert
Darstellungsattribute und elektrische Standardwerte. Die Änderung des
Referenz-Digests wurde unabhängig am abgenommenen Referenzcommit `d2fd035`
ermittelt, nicht aus der zu reparierenden Schaltung übernommen:

```text
Referenz d2fd035: 0d7893c6fbc0869006a4bd8ffa96313c405fac87719787ca1e71a3348159f980
Vor Korrektur:   2c5f7a1ab7ee9623f21c5b78661d718c024e3c388671a94b7e73f2355889241d
Nach Korrektur:  0d7893c6fbc0869006a4bd8ffa96313c405fac87719787ca1e71a3348159f980
```

Der vollständige Komponenten-/Port-/Netzvergleich stimmt somit wieder mit
der akzeptierten elektrischen Struktur überein, bei der aktuellen Zeichnung.
Zusätzliche Regressionen prüfen die sechs getrennten Fehler-Rückführungen,
den Fehlerhalt, gespeicherte Standardwerte und XML-Reihenfolge. Die beiden
Decoder-Negativkontrollen finden ihre Neutral-Konstanten über die Eingänge
12 beziehungsweise 14 von `ACC_LOAD_REQUEST`, weil auch Konstantenlabels
beim GUI-Speichern entfallen. Sie verändern ausschließlich Testkopien.

## Nachweise

Rohdaten und Bildexporte liegen lokal unter `artifacts/ap23-wiring-review/`.
Umgebung: Python 3.14.5, OpenJDK 27, vorhandene Logisim-evolution-4.1.0-JAR.
Für die Windows-Testläufe wurden `TEMP` und `TMP` auf
`artifacts/review-tmp` gesetzt; Java benötigt seine lokalen Benutzereinstellungen.

| Prüfung | Ergebnis / Nachweis |
|---|---|
| `python src/tiny_cpu_verify.py` | Bestanden; `verify-final.txt` |
| `python scripts/check-logisim-circuit.py` | Bestanden; `structure-final.txt` |
| `python -m unittest discover -s tests -v` | Alle 212 Tests bestanden; `unit-complete.txt` |
| `python src/tiny_cpu_logisim.py --java $env:JAVA --jar $env:LOGISIM_JAR --trace-output artifacts/ap23-wiring-review/final/core.tsv --matrix-output artifacts/ap23-wiring-review/final/matrix --jobs 4` | Zwei Minimalkernläufe, Countdown und alle 61 Kernfixtures bestanden; `core-final.txt` |
| `scripts/test-logisim-core-mutation.py` | Falscher ACC trotz normalen Halts abgewiesen; `checks-b.txt` |
| `scripts/test-logisim-store.py`, `test-logisim-print.py`, `test-logisim-immediate.py` | Positive Fälle und Negativkontrollen bestanden; `checks-a-final.txt` |
| `scripts/test-logisim-decode.py`, `test-logisim-address-register.py` | Decoder und Registerpfade einschließlich Mutationen bestanden; `checks-b-final.txt` |
| Systemmatrix mit `--system tinycpu-peripherals-16-12-v1 --system-only` | Alle sieben Fälle bestanden; `system.txt` |
| `scripts/test-logisim-operator.py` | Ein STEP-Takt ohne Wiederholung bei gehaltenem Eingang; `system.txt` |
| Logisim-Zeichen-API / Anschlussprüfung | Export gesichtet; `before.png`, `after.png`, `ports-before.tsv` |
| Layout- und Referenzvergleich | `topology-proof.json`; Komponenten unverändert, Teilkreise bytegleich |

Die Simulatorprüfungen verwenden das echte hierarchische Projekt. Die
abgeflachte Analyseansicht wird ausschließlich für Offline-Prüfungen erzeugt.

# INPUT-Resetkorrektur und Layout-Testreferenzen

Stand: 10. November 2026. Ausgangspunkt ist Commit
`02b058ce5bafaabe166e9ccbaa12bb830664d661` mit den zusÃ¤tzlichen lokalen
INPUT-TreiberÃ¤nderungen. Die eingegangenen Zeichnungen und Quellhashes wurden
unter `artifacts/input-reset-repair-20261110/before/` beziehungsweise
`incoming-hashes.json` gesichert.

**Abschluss:** Beide INPUT-Resetfehler und die sieben Layout-Testfehler sind
behoben. 294 Unit-Tests und alle 17 elektrischen Prüfpakete bestehen auf dem
endgültigen Schaltungsstand. Schritte 3 und 4 des Eingabeplans und damit
AP 22.1 sind abgeschlossen.

## Elektrisch belegte Ursachen und lokale Korrektur

Die passive Messung des zunÃ¤chst gescheiterten Reset-Falls bestÃ¤tigt:
`RESET=1` erreicht die Akkumulatorbox, `INPUT_CONSUME=0` sperrt korrekt,
aber `Datapath.ACC_LOAD=1`, `VALID_IN=1` und `DATA_IN=23` laden dennoch den
Akkumulator. Der Register-LÃ¶scheingang liegt vertragsgemÃ¤ÃŸ auf 0. Eine
zusÃ¤tzliche elektrische Kontrolle mit ungÃ¼ltigem Angebot belegt unabhÃ¤ngig
`ERROR_INPUT=1` wÃ¤hrend Reset. Beide Befunde sind vor der Reparatur erhalten:
`reset-passive.tsv` und `before-invalid/diagnostic.json`.

Nur drei Definitionen in `TinyCPU.circ` Ã¤ndern sich:

| Blatt | Korrektur |
| --- | --- |
| `AccumulatorInputUnit` | Zwei lokale Gatter: `G1 = NOT (CONTROL.34 AND RESET)` und `G2 = CONTROL.41 AND G1`. Nur G2 treibt `Datapath.ACC_LOAD`. |
| `FaultInputUnit` | ZusÃ¤tzlicher Reset-Eingang. `INPUT_FAILED = CONTROL.34 AND NOT INPUT_VALID AND NOT RESET`. |
| `CPUFaultInputUnitLink` | Greift RESET aus Bit 1 des bereits vorhandenen HOST-Busses ab und verbindet den neuen Blattanschluss. |

Takt, Datenwahl, GÃ¼ltigkeitswahl und Register-LÃ¶scheingÃ¤nge bleiben erhalten.
Die CPU behÃ¤lt ihre bisherige Resetsemantik: Der Befehlsablauf startet neu;
vorhandener Akkumulator, Adressregister, RAM und Sticky-Flags werden dadurch
nicht allgemein gelÃ¶scht. Die neue Sperre betrifft INPUT. Andere Befehle und
die Ã¶ffentliche Baseline-Schnittstelle werden nicht geÃ¤ndert.

Es kommen keine Konstanten, Tunnel oder eigenen Symbolformen hinzu. Neue
Gatter tragen kurze sichtbare Kennungen mit eigener ErklÃ¤rung unter der
Schaltung; SchriftgrÃ¶ÃŸen bleiben mindestens 10 Punkt. Die zusÃ¤tzlichen
Leitungen haben freie Korridore. Native Ansichten wurden kontrolliert; lange
ParallelfÃ¼hrungen und ODER-Anschlussrichtungen bestehen die bisherigen Regeln.

![INPUT-Ladesperre wÃ¤hrend Reset](images/input-reset-repair-20261110/accumulator.png)

![INPUT-Fehler nur auÃŸerhalb Reset](images/input-reset-repair-20261110/fault.png)

50 andere Kerndefinitionen und alle 23 Ã¼brigen `.circ`-Dateien bleiben
bytegleich, einschlieÃŸlich beider geschÃ¼tzter `FetchDecodeControls`.
UnverÃ¤nderte Komponenten und Leitungen behalten ihre XML-Darstellung.
Der endgÃ¼ltige SHA-256 von `TinyCPU.circ` ist
`83b18615e2692a3dd3ada11c3042e166654d85d4baf5e91e734f93b8f8bdc2ce`.
`source-proof.json` hÃ¤lt Abgrenzung und Bytevergleiche fest.

## Sieben Layout-Testfehler

Die sieben Subtestfehler betreffen sechs inzwischen weiter von Hand bearbeitete
Zeichnungen: `TinyCPUMain`, `EffectiveAddress`, `AddressPath`, `FetchDecode`,
`Operations` und `MulArithmeticCircuit`. `TinyCPUMain` wurde in zwei Methoden
beanstandet. Die Meldungen entstanden, weil die exakten Layoutreferenzen noch
den zuvor abgenommenen Stand beschrieben.

Vor der NachfÃ¼hrung wurden die tatsÃ¤chlichen nativen Logisim-AnschlÃ¼sse und
Netzpartitionen aller 53 KernblÃ¤tter mit dem zuvor abgenommenen Kandidaten aus
der Leitungskontrolle verglichen: gleiche Netze, gleiche Bitbreiten und gleiche
primitive Anschlussgeometrien. Die sechs aktuellen Zeichnungen wurden nativ
gesichtet und erhalten. Es war keine weitere Umzeichnung erforderlich.
`incoming-native-equivalence.json` bewahrt diesen Nachweis auf.

Nur die sechs betreffenden Referenzen und die drei lokal reparierten
INPUT-BlÃ¤tter wurden nachgefÃ¼hrt. Die strengen PrÃ¼fungen fÃ¼r neue oder
verÃ¤nderte Geometrien, tatsÃ¤chliche LeitungslÃ¼cken, AnschlÃ¼sse und Tunnel
bleiben aktiv. Die vorhandenen Regressionen gegen eine zusÃ¤tzliche unerlaubte
Leitung bleiben unverÃ¤ndert. Es wurde keine Assertion entfernt oder ein
fehlgeschlagener Test Ã¼bersprungen.

## Regression und verpflichtendes Gate

Die dynamische Matrix enthÃ¤lt nun 23 FÃ¤lle. Die drei ergÃ¤nzten FÃ¤lle prÃ¼fen
ungÃ¼ltiges Angebot wÃ¤hrend Reset, Halten eines bereits gÃ¼ltigen Akkumulators
sowie Halten von Akkumulator, RAM und Sticky-Flag Ã¼ber wiederholte Reset-Flanken.
Die Quelle wird erst bei der ersten ausgefÃ¼hrten INPUT-Flanke verbraucht.
Strukturtests prÃ¼fen beide Sperren und den durchgÃ¤ngigen Reset-Anschluss.

`scripts/test-logisim-input.py --baseline-matrix` fÃ¼hrt zusÃ¤tzlich alle 63
bestehenden Kernfixtures Ã¼ber `TinyCPUInputMain` mit Datenmuster 0 und
GÃ¼ltigkeit 0 aus. Die bisherigen Programme und absichtlich illegalen
ROM-WÃ¶rter bleiben erhalten; `rom-words.json` dokumentiert die tatsÃ¤chlich
injizierten WÃ¶rter. Jeder Fall behÃ¤lt den vollstÃ¤ndigen Vergleich von PC,
Registern, Flags, Ausgaben und RAM sowie das separate Verbrauchsprotokoll.

`scripts/test-logisim.sh` ruft diesen vollstÃ¤ndigen Eingabetest jetzt
verpflichtend auf. Eine Abweichung, ein Prozessfehler oder Timeout lÃ¤sst das
Gate scheitern. Die drei elektrischen Fehlerkopien fÃ¼r falsche Daten,
erzwungene GÃ¼ltigkeit und unterdrÃ¼ckten Verbrauch bleiben verpflichtend.

## AusfÃ¼hrung und Nachweise

Umgebung: Windows, Python 3.14.5, OpenJDK 27+35-2325 und die vorhandene
Logisim-evolution-JAR 4.1.0. Kein Download war erforderlich. PowerShell:

```powershell
New-Item -ItemType Directory -Force artifacts/input-reset-repair-20261110/tmp | Out-Null
$env:PYTHONPATH='src'
$env:JAVA='C:/Program Files/jdk-27/bin/java.exe'
$env:LOGISIM_JAR=(Resolve-Path .venv/Include/logisim-evolution-4.1.0-all.jar).Path
$env:TEMP=(Resolve-Path artifacts/input-reset-repair-20261110/tmp).Path
$env:TMP=$env:TEMP
$env:JAVA_TOOL_OPTIONS='-Djava.util.prefs.PreferencesFactory=LocalPreferencesFactory -Xbootclasspath/a:C:/Users/marku/myCloud/TinyCPU/artifacts/address-validity-20261104/prefs'
python src/tiny_cpu_verify.py
python scripts/check-logisim-circuit.py
python -m unittest discover -s tests -v
python scripts/test-logisim-input.py --baseline-matrix --output artifacts/input-reset-repair-20261110/electrical/input
```

Die lokale Preferences-Hilfsklasse umgeht nur das hier nicht beschreibbare
Windows-Preferences-Verzeichnis. Normale Installationen benÃ¶tigen sie nicht.
Ein MSYS-Bash-Start scheiterte in dieser Sandbox an einem Windows-IPC-Recht;
deshalb werden die Python-Aufrufe des Shell-Gates direkt und unverÃ¤ndert
ausgefÃ¼hrt. Exakte Befehle und Exitcodes stehen in `acceptance-results.json`.
Die lokale Orchestrierung ist unter `acceptance.py` im Artefaktordner erhalten.

Endgültige Ergebnisse unter `artifacts/input-reset-repair-20261110/`:

| Prüfung | Ergebnis |
| --- | --- |
| Offline-Verifikator und Schaltungsstruktur | Beide Exit 0; `verify-final.txt`, `structure-final.txt` |
| Windows-Unit-Suite | Alle 294 Tests bestanden; `unit-final.txt` |
| Dynamische INPUT-Abnahme | 23 Fälle, drei an der vorgesehenen ersten Beobachtung abgelehnte Fehlerkopien und 63 bestehende Kernfixtures mit inaktiver Eingabe bestanden; `electrical/input/proof.json` |
| Bestehende Kernabnahme | Beide Minimalkernläufe, Countdown und alle 63 Kernfixtures bestanden; `core-acceptance.txt` und `electrical/core/` |
| Arithmetische Grenzen | 83 vollständige Kern-/VM-Vergleiche, je 36 MUL- und DIV-Vektoren pro integrierter/Diagnosefassung sowie Negativkontrollen bestanden; `electrical/arithmetic-boundaries/proof.json` |
| Adressgültigkeit | 38 Fälle und drei abgelehnte Mutationen bestanden; `electrical/address-validity/proof.json` |
| System und Operator | Alle sieben Systemfälle, Taktarbitrierung und Operator-Kern-/VM-Vergleich einschließlich Negativkontrolle bestanden; `system-acceptance.txt`, `operator-acceptance.txt`, `operator-core-acceptance.txt` |
| Vorherige INPUT-Abnahme | Zehn statische Kern-/VM-Fälle, sieben Reset-Vektoren, drei Fehlerkopien und die passive Baseline bestanden; `electrical/input-boundary/proof.json`, `electrical/input-baseline/proof.json` |
| Gesamtumfang | Alle 17 Prüfpakete Exit 0, unveränderte Quellen während der Ausführung; `acceptance-results.json`, `final-proof.json` |

Die abschließende Korridorprüfung verwendet tatsächliche native Symbolkanten:
An beiden neuen Gattern, dem Verbrauchsgatter und dem Datapath bleiben die
geforderten 20 Pixel frei. Die dafür zuletzt verlegte Leitung ist durch einen
erneuten nativen Vergleich aller 53 Netzpartitionen und den vollständig
wiederholten elektrischen Lauf abgesichert. `corridor-proof.json` enthält
keine Befunde. `acceptance-before-corridors.json` bewahrt den zuvor ebenfalls
bestandenen funktionalen Lauf vor dieser letzten Layoutkorrektur auf.

Die QuellÃ¤nderungen sind auf diesen Windows-Kandidaten bezogen. Eine neue
Release-Abnahme aus frischem Checkout, ein Linux-CI-Lauf und eine interaktive
GUI-Bedienabnahme werden daraus nicht abgeleitet; diese bleiben eigene
Abnahmeaufgaben. Die nativen Bilder und Kontaktvergleiche ersetzen keine
interaktive BedienprÃ¼fung.

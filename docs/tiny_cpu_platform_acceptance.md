# AP 22.4: Offline-Abnahme unter Windows und Linux

Stand: 12. November 2026. **Status: Windows und WSL-Linux lokal bestanden;
Linux-CI wartet weiterhin auf einen Runner.**

## Nachprüfung des aktuellen Commits am 12. November

Der aktuelle Kandidat ist `0b9cf8db7ed1c89809c167a0ccf897e7cb694db2`,
Git-Tree `24b8c70d84329ea4ec44accce2bd81aafc1aefac`. Für die lokale
Plattformnachprüfung wurde dieser unveränderte Commit einmal mit
`git archive --format=tar` exportiert und getrennt je Betriebssystem entpackt.
SHA-256 des gemeinsamen Archivs:
`c2f3afce2679db0af4389d91201b54aafee957ca9e927ebc8fa446d6a100e04e`.
Die folgenden Berichtsänderungen gehören nicht zu diesem geprüften Commit.

Unter Windows 11 mit Python **3.14.5** bestehen Verifikator,
Strukturprüfung und alle **296 Unit-Tests** ohne Fehler oder übersprungene
Tests, jeweils mit Exitcode 0. Die Unit-Suite benötigt 85,706 Sekunden.
Die Pfad-Negativkontrolle besteht ebenfalls: Der vorhandene Download-Fehlertest
ist grün; ohne Vendor-Pfad in der Fehlermeldung scheitert genau eine Assertion.

Unter **Ubuntu 26.04.1 LTS / WSL2**, Kernel
`6.6.87.2-microsoft-standard-WSL2`, Python **3.14.4**, besteht dasselbe
vollständige Offline-Gate ebenfalls: Verifikator, Strukturprüfung und alle
**296 Unit-Tests**, keine Fehler oder übersprungenen Tests, Exitcode 0.
Die Unit-Suite benötigt 220,402 Sekunden, das gesamte Shell-Gate
226,220 Sekunden. Auch hier besteht der unveränderte Download-Fehlertest,
und die Negativkontrolle ohne Vendor-Pfad scheitert mit genau einer Assertion.

Ausgeführte Befehle ab Repository-Wurzel; das Nachweisverzeichnis war neu:

```powershell
python artifacts/platform-ap22-4-20261112/acceptance.py prepare
python artifacts/platform-ap22-4-20261112/acceptance.py windows
wsl -d Ubuntu --cd /mnt/c/Users/marku/myCloud/TinyCPU --exec python3 artifacts/platform-ap22-4-20261112/acceptance.py linux
```

Der Treiber entpackt das gemeinsame Archiv in `windows/source` beziehungsweise
`linux/source`. Unter Windows führt er die drei unten aufgeführten
Python-Aufrufe aus, unter Linux unverändert `bash scripts/test-offline.sh`.
Alle Gate-Aufrufe und beide Treiberläufe liefern Exitcode 0. Die erwartete
Assertion der getrennten Negativkontrolle ist in `path-missing-path.txt`
gesichert und zählt nicht als Fehler oder Skip der 296 Unit-Tests.

Das Archiv enthält auch die bereits versionierten `.venv`-Dateien. Sie werden
nicht aktiviert: Windows verwendet ausdrücklich
`C:/msys64/ucrt64/bin/python.exe`, Linux `/usr/bin/python3`. `PYTHONPATH` ist
für die Gate-Aufrufe entfernt. Es werden keine unversionierten lokalen Dateien
in die Quellsnapshots kopiert.

Der zum aktuellen Commit gehörende
[GitHub-Lauf 43096537405](https://github.com/MobyDickDick/TinyCPU/actions/runs/43096537405)
wartet ebenso wie der unten beschriebene Prüfbranch-Lauf weiterhin mit
`status=queued`, `conclusion=null` und ohne Jobs. Letzte Abfrage:
12. November 2026, **10:52 Uhr MEZ**. Ein lokaler WSL-Lauf ersetzt die
ausdrücklich geforderte Prüfung im bestehenden Linux-CI-Umfeld nicht;
**AP 22.4 bleibt offen**, bis deren vollständige Logs vorliegen.
Die Ursache der Runner-Wartezeit ist aus den abgefragten Run-/Jobdaten
nicht ersichtlich.

Neue lokale Nachweise: `artifacts/platform-ap22-4-20261112/` mit
`acceptance.py`, `candidate.json`, `candidate.tar`, `ci-status.json` sowie
plattformbezogenen `results.json`, Gate-Logs und Pfad-Negativkontrollen.
Die folgenden Abschnitte halten den Nachweis vom 11. November fest.

## Kandidat und Ausgangsbefund

Ausgangscommit: `4fc1c53891252e856aad816adfd446c96344f2b0`.
Der vorhandene Linux-Lauf
[43082911293](https://github.com/MobyDickDick/TinyCPU/actions/runs/43082911293)
brach unter Python 3.12.16 bereits im Verifikator bei der Layoutreferenz der
`AddressUnit` ab. Die vollständige Offline-Suite wurde dort deshalb nicht
ausgeführt. Die isolierte Windows-Wiederholung bestätigt den Befund:
Verifikator Exit 1, Strukturprüfung Exit 0, 296 Unit-Tests mit elf
fehlgeschlagenen Layout-Assertions. Der Download-Fehlerpfad bestand bereits.

Die jüngste Benutzerzeichnung wird erhalten. Ausschließlich zehn exakte
Geometrieeinträge in `hardware/logisim/layout-restoration-v1.json` sind nach
nativer Prüfung nachgeführt: `MulArithmeticCircuit`, `AddressUnit`,
`FaultUnit`, `BranchUnit`, `AddressRegisterLoad`, `AccumulatorInputUnit`,
`FaultInputUnit`, `CPUBranchUnitLink`, `CPUCoreDiagnosticsLink` und
`CPUStatusStage`. Keine Assertion wurde entfernt oder übersprungen.
Netz-, Schnittstellen-, Tunnel-, ODER-Anfahrts- und Parallelabstandsprüfungen
bleiben aktiv; die Referenz nimmt weiterhin nur die exakte Geometrie von der
Modulo-Rasterprüfung aus.

Native Vorher-/Nachher-Ansichten wurden mit Logisim-evolution 4.1.0 erzeugt.
Die 53 nativen Netzpartitionen und Anschlussgeometrien stimmen überein;
bei `FaultUnit.ADDRESS_INV_REQUEST` sind lediglich zwei nicht invertierte
ODER-Eingänge gleichwertig vertauscht. Der positionsunabhängige
Topologievergleich bestätigt die neun elektrisch umgelegten Blätter;
bei MUL ist ausschließlich die Position eines Textobjekts geändert.
Alle zehn Blätter bestehen zusätzlich je 64 native elektrische
Vergleichsschritte, zusammen **640 definierte, gleiche Zustände**.
Beide geschützten Decoder und sämtliche Schaltungsdateien bleiben in diesem
Arbeitspaket unverändert.

Die Sichtkontrolle erhält die Benutzeranordnung; sie behauptet keine neue
projektweite Layoutfreigabe. Bestehende, teilweise über Leitungen liegende
Gatterbeschriftungen bleiben ein Lesbarkeitspunkt außerhalb dieser
Plattformabnahme. Eine Umzeichnung wurde daraus nicht abgeleitet.

Der Linux-Prüfkandidat ist
[`cdba8e6e3ffa30ff4b3c78c9fdfeb38476ea5118`](https://github.com/MobyDickDick/TinyCPU/commit/cdba8e6e3ffa30ff4b3c78c9fdfeb38476ea5118)
auf `codex/ap22-4-platform-acceptance`. Gegenüber dem Ausgangscommit enthält
sein Quellbaum ausschließlich die oben genannte Referenzkorrektur.
Der lokale Windows-Snapshot verwendet denselben Quellinhalt; diese
Abschlussdokumentation und die später nachgeführten Statusseiten sind
Berichtsänderungen außerhalb des geprüften Quellkandidaten.

## Windows-Nachweis

Windows 11, Python **3.14.5**. Der frisch aus `git archive HEAD` extrahierte
Quellsnapshot enthält die nachgeführte Referenzdatei und die versionierten
`.venv`-Dateien; das Gate verwendet den externen Python-Interpreter ohne
Aktivierung dieser Umgebung. Vorhandene unversionierte Artefakte werden nicht
übernommen. `PYTHONPATH` ist entfernt. Temporäre Dateien liegen im
Nachweisverzeichnis.

```powershell
python src/tiny_cpu_verify.py
python scripts/check-logisim-circuit.py
python -m unittest discover -s tests -v
```

Alle drei Aufrufe liefern **Exitcode 0**. Alle **296 Tests** bestehen ohne
Fehler oder übersprungene Tests. Dazu gehören die sechs veröffentlichten
Programmläufe und die aktuellen lokalen Dokumentationslinks.

Der unveränderte Test
`test_missing_vendored_jar_is_named_when_download_fails` provoziert weiterhin
einen echten Download-Fehler bei fehlenden lokalen JARs. `re.escape()` trennt
den Literalpfad vom regulären Ausdruck. Eine zusätzliche Laufzeitmutation
führt denselben Test erneut aus, entfernt aber den Vendor-Pfad aus der
geworfenen Fehlermeldung: genau diese Assertion schlägt dann erwartungsgemäß
fehl. Die unveränderte Variante besteht. Die Negativkontrolle verändert keine
produktive Datei und ist kein übersprungener Unit-Test.

## Linux-Nachweis

Der bestehende Workflow `.github/workflows/tests.yml` soll auf dem Prüfbranch
unverändert `scripts/test-offline.sh` mit Python 3.12 ausführen.
[Prüflauf 43095292624](https://github.com/MobyDickDick/TinyCPU/actions/runs/43095292624)
ist angenommen, wartet aber noch auf einen Runner; es gibt noch keine Jobs
oder Testergebnisse. **AP 22.4 bleibt deshalb offen.** Ein angenommener
Workflowlauf ist kein bestandener Linux-Nachweis.
Letzte Prüfung: 11. November 2026, **21:28 Uhr MEZ**; seit 21:19 Uhr
MEZ unverändert `queued`. `ci-status.json` hält diesen beobachteten Stand fest.
Nach erfolgreichem Jobabschluss müssen dessen vollständige Logs, tatsächliche
Python-Version, Testanzahl und Exitcode gesichert und erst danach die
AP-22.4-Checkbox sowie die aktuellen Statusseiten abgeschlossen werden.

## Lokale Artefakte und Grenze

Nachweisverzeichnis: `artifacts/platform-ap22-4-20261111/`.

- `acceptance.py`, `candidate-files.json`, `results.json`, `verify.txt`,
  `structure.txt`, `unit.txt`: Quellsnapshot, Inventar, Befehle und Exitcodes.
- `windows-before/` und `linux-offline-before.txt`: reproduzierter roter
  Ausgangsstand und ursprünglicher CI-Fehler.
- `drawing-review.json`, `native-net-proof.json`, `native-before/`,
  `native-after/`: Geometrie-, Topologie-, native Anschluss- und Bildnachweise.
- `native-equivalence.txt`, `source-proof.json`: 640 native Vergleichsschritte
  sowie Schaltungs- und Referenzdatei-Digests. Die Referenzdatei besitzt lokal
  und im Linux-Prüfcommit denselben Git-Blob `530e7e8f9cb381193dd7d706111f244db11a54b4`.
- `path-negative-control.py`, `path-negative-control.json`,
  `path-original.txt`, `path-missing-path.txt`: tatsächliche Ausführung und
  gezielte Ablehnung der Fehlermeldung ohne Pfad.
- `ci-status.json`: Prüfcommit, Workflowlauf und zuletzt tatsächlich
  beobachteter Wartestatus ohne Linux-Testergebnis.

AP 22.5 bleibt ein eigenes Arbeitspaket: gemeinsame Neuabnahme von Offline-,
vollständigem elektrischem Kern-/System- und Operator-Gate auf demselben
Kandidaten mit vollständigem Versions- und Artefaktprotokoll. Die manuelle
GUI-Kurzabnahme bleibt ebenfalls offen. Native Bildausgabe und automatische
elektrische Vergleichsschritte ersetzen keine sichtbare Bedienprüfung.

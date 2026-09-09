# AP 19: Diagnosebericht zu `TinyCPU.circ`

Dieser Bericht wird entlang der zehn Aufgaben aus
`tiny_cpu_circuit_debug_plan.md` fortgeschrieben. Er trennt nachgewiesene
Fehler von noch nicht reproduzierten Beobachtungen. Die manuell gepflegte
Schaltung wird insbesondere nicht allein aufgrund eines Tests mit historischen
Canvas-Koordinaten verändert.

## Status

| Aufgabe | Status | Ergebnis |
|---|---|---|
| 19.1 Fehlerbild und Baseline einfrieren | abgeschlossen | Baseline und Umgebung sind festgehalten; die Offline-Suite reproduziert zwei Fehler, der elektrische Lauf ist mangels Simulator-JAR noch offen. |
| 19.2 Projektladung und Hierarchie isolieren | abgeschlossen | Alle drei Smoke-Projekte, 24 Diagnoseblätter und `TinyCPU.circ` laden mit Logisim-evolution 4.1.0 fehlerfrei; die Strukturprüfung findet weder Hierarchie- noch Leitungsfehler. |
| 19.3 Takt, Reset, PC und Fetch prüfen | als Nächstes | Reset und die ersten Fetch-Flanken müssen elektrisch gegen den VM-Kerntrace geprüft werden. |
| 19.4–19.10 | offen | Noch nicht begonnen. |

## 19.1 Fehlerbild und Baseline einfrieren

### Ausgangslage

- **Zeitpunkt:** 2026-09-09T17:09:11Z
- **Ausgangs-Commit:**
  `9e0e263ad0e97a7ad65fff742f0fff1049eec22b`
- **Arbeitsbaum vor der Untersuchung:** sauber (`git status --porcelain`
  lieferte keine Ausgabe).
- **Schaltungsquelle:** ausschließlich
  `hardware/logisim/TinyCPU.circ` aus dem genannten Commit; keine historische
  Zeichnung wurde herangezogen oder eingespielt.
- **Vorgesehenes Startblatt:** `TinyCPUMain` im unveränderten 16/12-Profil.
- **Umgebung:** OpenJDK 25.0.2, Python 3.14.4. Die gepinnte
  Logisim-evolution-Version ist 4.1.0; deren JAR war weder unter
  `vendor/` noch im lokalen Cache vorhanden.

Die zu prüfende Bedienfolge ist: Projekt in Logisim-evolution 4.1.0 öffnen,
`TinyCPUMain` wählen, Reset auslösen und anschließend den Takt schrittweise
fortschalten. Erwartet werden ein deterministischer Start bei Instruktion 0,
die Ausgabe des eingelegten Countdown-Programms und ein normaler Halt. Diese
GUI-Beobachtung ist in dieser Aufgabe **nicht reproduziert**, weil die
unterstützte Simulatorversion nicht gestartet werden konnte.

### Kommando oder Bedienfolge

Die Baseline wurde ohne Änderungen an der Schaltung mit folgenden Kommandos
aufgenommen:

```bash
git rev-parse HEAD
git status --porcelain
java -version
python3 --version
scripts/test-offline.sh
LOGISIM_OUTPUT=/tmp/tinycpu-ap19.1-baseline/electrical \
  scripts/test-logisim.sh
```

Die vollständigen Ausgaben liegen lokal unter
`artifacts/ap19.1-baseline/`. Das Verzeichnis ist bewusst von Git
ausgeschlossen: Es enthält Laufartefakte und keine Schaltungsquelle. Die drei
Baseline-Dateien besitzen folgende SHA-256-Digests:

```text
504b21bb240c4c0b0dda2d2e5ce310780584d68299fdcfe33df6bb30c3daff22  environment.txt
b26317e709e59851f90614330ed806c8c5f4f2f40070a0192dfbe984ee90e44d  test-offline.log
5ec171a469ff975556be09ab7af5819b4b0c6a118c5ad6284b248b8ae58b84ae  test-logisim.log
```

### Beobachteter Nachweis

Die strukturelle Vorprüfung selbst akzeptierte 14 JSON-Dateien, 30
Logisim-Dateien mit 81 Schaltungen und 4579 orthogonalen Leitungen sowie den
Vertrag aus 50 Opcodes und sechs Sticky-Fehler-Fixtures. Danach liefen 64
Unit-Tests; 62 bestanden und zwei schlugen fehl:

1. `test_add_operand_reaches_operations_input` meldet, dass
   `TinyCPU.circ` den Addition-Enable-Eingang nicht über die im Test erwartete
   Route treibt.
2. `test_sub_operand_reaches_operations_input` erwartet den Pin
   `SUB_OPERAND` bei `(330,470)`, findet ihn aber bei `(340,610)`.

Damit ist ein wiederholbares Baseline-Fehlerbild vorhanden. Es ist jedoch noch
**kein belegter Schaltungsfehler**: Beide Tests vergleichen feste
Canvas-Koordinaten beziehungsweise Leitungssegmente und widersprechen damit
dem aktuellen topologischen Testvertrag. Insbesondere der zweite Fehler kann
eine bloße Layoutänderung sein. Vor einer Reparatur muss Aufgabe 19.2 die
Projekte laden und eine folgende Aufgabe den Übergang über benannte Ports
elektrisch oder topologisch nachweisen.

Der elektrische Befehl versuchte wie vorgesehen beide Profile. Beide brachen
vor dem Laden eines Projekts ab, weil
`logisim-evolution-4.1.0-all.jar` lokal fehlte und der Download durch den
Netzwerk-Proxy mit HTTP 403 abgewiesen wurde. Daher gibt es weder einen
elektrischen Trace noch ein erstes fehlerhaftes Taktereignis. Der früheste
nachgewiesene Fehler liegt vielmehr vor Takt 0 in der Offline-Abnahme. Eine
allgemeine Beobachtung „CPU funktioniert nicht“ bleibt ausdrücklich offen.

### Offene Risiken und Übergabe an 19.2

- Die Ladefähigkeit von Smoke-Projekten, Diagnoseblättern und
  `TinyCPU.circ` ist mit Logisim-evolution 4.1.0 noch nicht belegt.
- Countdown, Opcode-Matrix und Sticky-Fehlerfälle wurden elektrisch noch nicht
  ausgeführt; über den ersten abweichenden Takt kann deshalb keine Aussage
  getroffen werden.
- Die zwei Offline-Fehler können veraltete, koordinatengebundene Regressionen
  statt elektrische Defekte anzeigen. Sie dürfen keine Neuverdrahtung auf
  Verdacht auslösen.
- Aufgabe 19.2 benötigt die unveränderte gepinnte JAR. Danach sind zuerst die
  drei `smoke/`-Projekte, anschließend die erzeugten Diagnoseblätter und erst
  zuletzt `TinyCPU.circ` mit Startdauer und Simulatorprotokoll zu prüfen.

## 19.2 Projektladung und Hierarchie isolieren

### Ausgangslage

Die in 19.1 fehlende, unveränderte Logisim-evolution-JAR war für diesen Lauf
unter `.venv/Include/logisim-evolution-4.1.0-all.jar` verfügbar und meldete
Version 4.1.0. Untersucht wurde weiterhin ausschließlich die Schaltungsquelle
des in 19.1 festgehaltenen Ausgangsstands. Die Stufen bestanden aus den drei
Projekten in `smoke/`, allen 24 eingecheckten Diagnoseprojekten und zuletzt dem
integrierten Hauptprojekt.

### Kommando oder Bedienfolge

Jede Datei wurde in einem eigenen JVM-Prozess mit einem Zeitlimit von 30
Sekunden geladen. Der Modus `stats` erzwingt das Parsen und Aufbauen der
ausgewählten Projekthierarchie, beendet sich anschließend aber ohne Taktlauf:

```bash
timeout 30s java -jar .venv/Include/logisim-evolution-4.1.0-all.jar \
  -tty stats PROJEKT.circ
```

Die Reihenfolge war `hardware/logisim/smoke/*.circ`, danach
`hardware/logisim/diagnostics/*.circ` und schließlich
`hardware/logisim/TinyCPU.circ`. Für jeden Prozess wurden Exitcode, monotone
Laufzeit, Standardausgabe und Standardfehler erfasst. Die lokalen Rohdaten
liegen unter `artifacts/ap19.2-load/` und bleiben wie vorgesehen außerhalb von
Git. Anschließend prüfte

```bash
PYTHONPATH=src python3 src/tiny_cpu_verify.py
```

projektspezifische Unterblattverweise und Rekursion sowie sämtliche Leitungen
auf diagonale oder identische Endpunkte.

### Beobachteter Nachweis

Alle **28 Projekte** wurden in der vorgesehenen Reihenfolge geladen und
lieferten Exitcode 0 ohne Ausgabe auf Standardfehler:

| Stufe | Projekte | Laufzeit pro Projekt | größter beobachteter RSS |
|---|---:|---:|---:|
| Smoke | 3 | 1,076–1,167 s | 88.536 KiB |
| Diagnoseblätter | 24 | 1,207–1,466 s | 97.624 KiB |
| `TinyCPU.circ` | 1 | 1,676 s | 109.920 KiB |

Damit gibt es keine erste scheiternde Ladestufe. Die Hauptdatei meldete 421
Bauteilinstanzen ohne und 470 Instanzen mit aufgelösten Unterblättern. Die
ergänzende Strukturprüfung akzeptierte 30 Logisim-Dateien mit 81 Schaltungen
und 4579 orthogonalen Leitungen. Sie fand keine fehlenden Unterblätter, keinen
Hierarchiezyklus und weder diagonale noch Null-Längen-Leitungen. Der moderate
Anstieg von Laufzeit und Speicherbedarf bis zur Integration ist kein Hinweis
auf auffälligen Ressourcenverbrauch oder unendliche Rekursion.

Die in 19.1 beobachteten koordinatengebundenen Unit-Testfehler sind damit nicht
auf einen Parser-, Hierarchie- oder allgemeinen Ladefehler zurückzuführen. Aus
dem reinen Ladelauf folgt jedoch noch nicht, dass die betreffenden Netze oder
der Prozessor elektrisch korrekt arbeiten.

### Offene Risiken und Übergabe an 19.3

- Der Lauf verwendete die vorhandene OpenJDK-Version 25.0.2 statt des für die
  vollständige Abnahme gepinnten Temurin 21.0.8. Da alle Projekte mit der
  korrekten Logisim-Version geladen wurden, ist die Hierarchie eingegrenzt;
  die finale elektrische Regression muss dennoch die gepinnte Java-Version
  verwenden.
- `-tty stats` lädt und expandiert die Hierarchie, taktet die Schaltung aber
  nicht. Elektrische Probleme in Reset, Fetch oder Datenpfad bleiben möglich.
- Die beiden Offline-Unit-Testfehler aus 19.1 bleiben als mögliche veraltete
  Layoutannahmen offen. Sie rechtfertigen weiterhin keine Verdrahtungsänderung.
- Aufgabe 19.3 beginnt deshalb ohne Schaltungsänderung mit einem Reset und dem
  kleinsten Fetch-Trace. Erst die erste abweichende Flanke beziehungsweise ein
  abweichender benannter Port darf die weitere Diagnose bestimmen.

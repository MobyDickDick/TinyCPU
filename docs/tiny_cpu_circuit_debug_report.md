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
| 19.2 Projektladung und Hierarchie isolieren | als Nächstes | Smoke-Projekte, Diagnoseblätter und Hauptprojekt müssen mit Logisim-evolution 4.1.0 geladen werden. |
| 19.3–19.10 | offen | Noch nicht begonnen. |

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

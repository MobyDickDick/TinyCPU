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
| 19.3 Takt, Reset, PC und Fetch prüfen | abgeschlossen mit Abweichung | Das Minimalprogramm erreicht elektrisch keinen Halt. Der erste bereits vor Takt 0 abweichende benannte Fetch-Eingang ist `PROGRAM_LIMIT`: `TinyCPUMain` treibt ihn konstant mit 0 statt mit der Profilgrenze `0xfff`. Zwei Reset-Läufe sind fachlich identisch. |
| 19.4 Decoder-Steuerfläche vollständig abgleichen | abgeschlossen mit Abweichung | Die elektrische 64-Zeilen-Tabelle stimmt nur für die reservierten Codes 54–63: `FetchDecodeControls` dekodiert eine veraltete, gegenüber dem Maschinenformat verschobene Belegung. |
| 19.5 Akkumulator und Rechenpfad debuggen | abgeschlossen mit Abweichung | Der isolierte Akkumulator schreibt Wert und Validität gemeinsam; 12 von 20 Operationsfällen stimmen. Speicherwahl, Invalidität, Multiplikationsüberlauf und Division weichen bereits im kombinatorischen Blatt ab. |
| 19.6 Adresspfad und Speicher debuggen | abgeschlossen mit Abweichung | Adressregister und beide RAMs arbeiten gekoppelt; `EffectiveAddress` wählt Direkt-/Registeradresse und Offset jedoch mit vertauschter zweiter Multiplexerpolarität, wodurch auch die Bereichsprüfung die falsche Adresse bewertet. |
| 19.7 Sprünge, Ausgabe, Halt und Fehlerflags prüfen | abgeschlossen mit Abweichung | Fünf Sprungsteuersignale enden nur an Monitoren; die vier Enable-/Halteausgänge sind vollständig unverdrahtet. Die sechs Sticky-Flags sind dagegen set-dominant und gemeinsam löschbar aufgebaut. |
| 19.8 Ersten abweichenden Netzübergang minimal reparieren | abgeschlossen | Achtzehn belegte Übergänge sind repariert; zuletzt wurde `JUMP_NOT_ERROR` mit der invertierten Sammelfehlerbedingung an den gemeinsamen PC-Auswahlpfad angeschlossen. |
| 19.9 Vollständige elektrische Regression und GUI-Kurztest | teilweise abgeschlossen | Nach der Redraw-Korrektur bestehen Offline-Suite, 16/12-Kerntrace und alle 61 zugehörigen Fixtures. Der unveränderte 8/8-Kerntrace erreicht unter der verfügbaren JDK-Version weiterhin keinen Halt; auch der manuelle GUI-Kurztest bleibt offen. |
| 19.10 Funktionsfähigen Kandidaten einfrieren | offen | Erst nach einer bestandenen elektrischen Abnahme zulässig. |

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

## 19.3 Takt, Reset, PC und Fetch prüfen

### Ausgangslage

Die Untersuchung blieb auf der in 19.1 festgehaltenen Schaltungsquelle. Als
kleinstes Fetch-Programm wurden genau zwei Wörter in eine temporäre Kopie des
Instruktions-ROMs geschrieben:

```text
0: LOAD_CONST(7)  = 0x000007
1: HALT()         = 0x2c0000
```

Die VM beginnt damit bei `PC=0`, übernimmt an der ersten Flanke den Wert 7 und
steht bei `PC=1`; an der zweiten Flanke führt sie `HALT` aus und steht bei
`PC=2` im normalen Halt. Es werden weder ein Bereichsfehler noch ein
Fehlerhalt erwartet. Die Schaltung wurde nicht geändert. Insbesondere sind
die nachfolgenden Versuche ausschließlich temporäre Dateien unter `/tmp` und
keine neue Schaltungsquelle.

### Kommando oder Bedienfolge

Das Programm wurde mit `assemble()` und `encode_program()` aus den bestehenden
Python-Modulen erzeugt. `autonomous_project()` ersetzte in einer temporären
Kopie nur `CLK` durch den Simulator-Takt, `RESET` durch `PowerOnReset`, den
ROM-Inhalt durch die beiden Wörter und den gewählten normalen Haltausgang durch
den von Logisim erwarteten Namen `halt`. Anschließend liefen zwei unabhängige
Reset-/Taktversuche mit Logisim-evolution 4.1.0:

```bash
PYTHONPATH=src python3 - <<'PY'
from pathlib import Path
from tiny_cpu_assembler import assemble, encode_program
from tiny_cpu_logisim import autonomous_project
from tiny_cpu_profiles import load_profile

profile = load_profile("tinycpu-16-12")
program = assemble("LOAD_CONST(7)\nHALT()\n", profile)
for run in (1, 2):
    autonomous_project(
        Path("hardware/logisim/TinyCPU.circ"),
        Path(f"/tmp/ap19.3-fetch-{run}.circ"),
        profile.top_circuit,
        tuple(encode_program(program)),
    )
PY

for run in 1 2; do
  timeout 30s /root/.local/share/mise/installs/java/21.0.2/bin/java \
    -jar .venv/Include/logisim-evolution-4.1.0-all.jar \
    -tty table,halt "/tmp/ap19.3-fetch-$run.circ" \
    >"/tmp/ap19.3-fetch-$run.tsv"
done
```

Zusätzlich wurden die `FetchDecode`-Portreihenfolge und die angeschlossene
Konstante direkt aus dem aktuellen XML gelesen. Der fünfte linke Eingang des
Symbols ist laut gepflegtem Unterblatt `PROGRAM_LIMIT` (16 Bit). Auf
`TinyCPUMain` endet dessen Netz an der 16-Bit-Konstante bei `(660,430)`. Die
Konstante besitzt kein `value`-Attribut und hat nach Logisim-Semantik daher den
Wert 0. Das Profil und das Unterblatt erwarten dagegen die 12-Bit-Grenze
`0xfff`.

### Beobachteter Nachweis

Beide elektrischen Läufe erreichten `halt` nicht und wurden nach 30 Sekunden
beendet. Vor dem Stillstand lieferte jeder Lauf dieselben vier Tabellenzeilen;
beide Rohtraces hatten denselben SHA-256-Digest
`c40de99880802f043459bebda80066816802d30761f89e1237d7e0a377cedd21`.
Der erste Zustand war definiert null. Nach der ersten Flanke erschien wie von
der VM erwartet der Akkumulatorwert 7 am Ausgabebus. Danach wurden jedoch erst
einzelne und schließlich fast alle beobachteten Signale mit Logisims
Fehlerwert `E` belegt; der normale Haltausgang blieb aus. Der elektrische Trace
weicht damit spätestens beim Übergang zu Instruktion 1 vom VM-Trace ab.

Die Eingrenzung findet einen noch früheren, benannten Unterschied: Bereits vor
Takt 0 sieht `FetchDecode.PROGRAM_LIMIT` am Top-Level den Wert 0, obwohl das
16/12-Profil und der Default des isolierten Unterblatts `0xfff` vorgeben. Somit
ist schon die Fortschaltung von `PC=0` nach `PC=1` außerhalb der elektrisch
erlaubten Programmgrenze. Das erklärt den verfrühten Bereichsfehlerpfad, belegt
aber noch nicht, dass es die einzige Ursache der späteren `E`-Werte ist. Ein
Kontrolllauf, der ausschließlich in einer temporären Kopie diese Konstante auf
`0xfff` setzte, erzeugte weiterhin die gleichen vier Zeilen. Entsprechend wird
hier weder eine Reparatur behauptet noch eine Änderung an `TinyCPU.circ`
vorgenommen.

Das Reset-Kriterium ist reproduzierbar: Beide frischen autonomen Projekte
starteten mit demselben definierten Nullzustand und erzeugten denselben
fachlichen Verlauf. Das vollständige Abnahmekriterium (elektrische Parität bis
zum normalen Halt) besteht dagegen nicht. Aufgabe 19.3 ist als Diagnoseaufgabe
mit belegter Abweichung abgeschlossen; die minimale Reparatur bleibt gemäß
Paketreihenfolge Aufgabe 19.8 vorbehalten.

### Offene Risiken und Übergabe an 19.4

- Der Lauf verwendete das lokal verfügbare Java 21.0.2. Die in der
  Kompatibilitätsmatrix vorgesehene Temurin-Version 21.0.8 muss spätestens in
  19.9 erneut verwendet werden; die identischen Resultate mit Java 25.0.2
  sprechen derzeit gegen eine reine JVM-Abweichung.
- `PC_OUT` und das ROM-Wort sind im Unterblatt benannt, aber nicht als
  Top-Level-Tabellenspalten exportiert. Die Eingrenzung beruht deshalb auf dem
  benannten Portvertrag, dem fest verdrahteten `PROGRAM_LIMIT`-Netz und den
  beobachtbaren Endpunkten, nicht auf vermuteten Canvas-Koordinaten eines
  historischen Standes.
- Die temporäre Korrektur von `PROGRAM_LIMIT` beseitigte die späteren
  Fehlerwerte nicht. Weitere Abweichungen sind wahrscheinlich und werden nicht
  vorgezogen repariert.
- Aufgabe 19.4 prüft nun die Decoder-Steuerfläche. Der Befund zu
  `PROGRAM_LIMIT` bleibt für 19.8 als erster nachgewiesener Übergang
  `Konstante → FetchDecode.PROGRAM_LIMIT` vorgemerkt.

## 19.4 Decoder-Steuerfläche vollständig abgleichen

### Ausgangslage

Untersucht wurde weiterhin unverändert `FetchDecodeControls` aus der in 19.1
festgehaltenen Schaltungsquelle. Fachliches Orakel war die 6-Bit-Belegung aus
`tinycpu-machine-v1.json`: Sie definiert 50 Opcodes mit den Codes 0 bis 49;
die Codes 50 bis 63 sind reservierte Negativfälle. Die erwartete
Steuerfläche wurde aus Mnemonik und Adressierungsart abgeleitet:

- genau ein zur Instruktionsfamilie passendes Operationssignal und bei
  Operandenbefehlen genau eine passende Argumentquelle;
- bei `NOT`, Sprüngen, E/A, `CLEAR_ERROR` und den beiden Haltarten genau der
  jeweilige Direktausgang;
- `INVALID_OPERAND` und kein anderer Ausgang bei jedem reservierten Code;
- kein direktes `SET_*`-Signal allein durch einen gültigen Opcode. Diese
  Leitungen melden Laufzeitfehler und sind keine zusätzlichen Maschinenbefehle.

### Kommando oder Bedienfolge

Eine temporäre XML-Kopie setzte lediglich das Projekt-Startblatt auf das
vorhandene Unterblatt `FetchDecodeControls`; die eingecheckte Schaltung blieb
unverändert. Logisims Tabellenmodus enumerierte daraufhin automatisch alle
64 Kombinationen des sechsbittigen Eingabepins und exportierte alle 33
Steuerausgänge:

```bash
python3 - <<'PY'
import xml.etree.ElementTree as ET

tree = ET.parse("hardware/logisim/TinyCPU.circ")
tree.getroot().find("main").set("name", "FetchDecodeControls")
tree.write("/tmp/ap19.4-decode.circ", encoding="utf-8", xml_declaration=True)
PY

timeout 30s /root/.local/share/mise/installs/java/21.0.2/bin/java \
  -jar .venv/Include/logisim-evolution-4.1.0-all.jar \
  -tty table /tmp/ap19.4-decode.circ \
  > artifacts/ap19.4-decode/fetch-decode-controls.tsv
```

Ein Python-Vergleich lud anschließend die Opcode-Tabelle über
`opcode_table(load_profile("tinycpu-16-12"))`, erzeugte für jeden Code die
erwartete Ein-Hot-Steuerzeile und verglich jede Zelle der elektrischen Tabelle.
Die lokale Zusammenfassung und der vollständige zellenweise Unterschied liegen
unter `artifacts/ap19.4-decode/`. Wie die vorherigen Rohdaten bleibt dieses
Verzeichnis außerhalb von Git. Die Nachweise besitzen folgende Digests:

```text
ff80c5cc0460b29572ec117c3286daa7777f1df2867484b2a0267be928134666  fetch-decode-controls.tsv
4b6447124baf6c83fe71698ab71db576a00ba7fccff36194585ca248bc30e146  comparison.json
62d411c8211d7d60da4c51e4a7c79639f911b6b4b89e773789ce73c84d2ba7b8  summary.txt
```

### Beobachteter Nachweis

Der Simulator lieferte 64 vollständig definierte Zeilen ohne schwebende oder
fehlerhafte Ausgangswerte. Innerhalb seiner tatsächlichen Belegung hält der
Decoder den gegenseitigen Ausschluss ein: Höchstens ein Operationssignal,
höchstens eine Argumentquelle und höchstens ein Direktsignal sind aktiv. Diese
elektrische Belegung ist jedoch nicht die versionierte Maschinenbelegung.

Nur **10 von 64 Zeilen** stimmen vollständig; dies sind die reservierten Codes
54 bis 63. Die Codes 0 bis 53 weichen in insgesamt **120 Ausgangszellen** ab.
Der erste Unterschied liegt bereits bei Code 0: `LOAD_CONST` müsste
`LOAD_OPERAND + CONST_ARGUMENT` liefern, elektrisch erscheinen aber
`ADD_OPERAND + CONST_ARGUMENT`. Danach zeigt sich eine durchgängige alte
Gruppierung:

| Codes | Versioniertes Maschinenformat | Elektrischer Decoder |
|---:|---|---|
| 0–3 | `LOAD_*` | `ADD_OPERAND` |
| 4–27 | `ADD_*` bis `OR_*` | `SUB_OPERAND` bis `XOR_OPERAND` |
| 28–34 | `STORE_*`, Adressregister-Laden, `NOT`, `JUMP_ADDRESS` | `LOAD_OPERAND`, `STORE_OPERAND` |
| 35–41 | Sprünge, `CLEAR_ERROR`, `INPUT` | `NOT`, Sprünge bis `JUMP_NOT_ERROR` |
| 42–47 | `PRINT`, `PRINT_ADDRESS`, Haltarten, `XOR_CONST`, `XOR_ADDRESS` | `SET_OVF` bis `SET_INPUT` |
| 48–49 | `XOR_ADDRESS_REGISTER*` | `CLEAR_ERROR`, `INPUT` |
| 50–53 | reserviert | `PRINT`, `PRINT_ADR`, `HALT`, `HALT_ERROR` |
| 54–63 | reserviert | `INVALID_OPERAND` |

Damit sind weder vertauschte Top-Level-Pins noch ein einzelnes
zusammengeführtes Steuernetz die Hauptabweichung. `FetchDecodeControls` setzt
seinen 6-zu-64-Decoder konsistent auf eine ältere 54-Code-Steuerreihenfolge um,
während ROM, Assembler und VM die eingefrorene 50-Code-Tabelle verwenden. Der
Befund erklärt, warum das Minimalprogramm aus 19.3 mit Maschinenopcode 0 nicht
als `LOAD_CONST` gesteuert wird. Er liegt ebenfalls bereits vor der ersten
Taktflanke, wird aber wegen der Paket-Stop-Regel noch nicht repariert.

### Offene Risiken und Übergabe an 19.5

- Die Tabelle isoliert bewusst nur `FetchDecodeControls`. Ob zusätzliche Fehler
  zwischen dessen Ausgängen und Datenpfad, Speicher oder Endpunkten liegen,
  bleibt offen.
- Der Lauf nutzte erneut Java 21.0.2 statt Temurin 21.0.8. Er verwendete aber
  die gepinnte Logisim-evolution-Version 4.1.0 und erzeugte ausschließlich
  binäre, reproduzierbare Kombinationswerte; die Abschlussabnahme in 19.9 muss
  dennoch die vollständig gepinnte Umgebung wiederholen.
- Die Korrektur muss in 19.8 die Decoder-Ausgänge auf die aktuelle
  Maschinenbelegung abbilden und zugleich die reservierten Codes 50 bis 63 auf
  `INVALID_OPERAND` legen. Eine großflächige Neuverdrahtung vor Abschluss der
  Diagnoseaufgaben bleibt ausgeschlossen.
- Aufgabe 19.5 verfolgt als Nächstes kleine Lade-, `NOT`-, Arithmetik- und
  Logikprogramme von der gewählten Argumentquelle bis zum Akkumulator. Wegen
  der nachgewiesenen Decoder-Verschiebung muss sie den erwarteten und den
  tatsächlich aktivierten Steuerzweig getrennt protokollieren.

## 19.5 Akkumulator und Rechenpfad debuggen

### Ausgangslage

Die Decoderabweichung aus 19.4 verhindert weiterhin, dass ein Maschinenwort
am integrierten Top-Level zuverlässig die beabsichtigte Operation auswählt.
Damit dieser bekannte vorgelagerte Fehler keine Datenpfadfehler verdeckt,
wurde das vorhandene Blatt `Operations` direkt über seine **benannten Pins**
angeregt. Untersucht wurden Laden aus Konstante und Speicher, `NOT`, alle
sieben binären Familien, Null und die vorzeichenbehafteten Grenzen sowie
ungültige Akkumulator- und Speicheroperanden. Das Blatt `Datapath` wurde
anschließend separat mit einem autonomen Takt geprüft. Die eingecheckte
Schaltung blieb bei beiden Untersuchungen unverändert.

### Kommando oder Bedienfolge

Ein lokales Python-Skript erzeugte für 20 Fälle je eine temporäre Kopie,
wählte `Operations` als Startblatt und ersetzte ausschließlich dessen
benannte Eingabepins durch gleich breite Konstanten. Jede Kopie wurde mit
Logisim-evolution 4.1.0 ausgeführt:

```bash
PYTHONPATH=src python3 /tmp/run_ap195.py

/root/.local/share/mise/installs/java/21.0.2/bin/java \
  -jar .venv/Include/logisim-evolution-4.1.0-all.jar \
  -tty table /tmp/ap195-FALL.circ
```

Der Vergleich berechnete die erwarteten 16-Bit-Ergebnisse und Statussignale
nach dem VM-Vertrag und verglich `RESULT_VALUE`, `OVERFLOW`,
`RESULT_IS_VALID`, `INVALID_OPERAND` und `DIVIDE_BY_ZERO`. Für den
Akkumulatortest wurden `DATA_IN=0x8000`, `ACC_LOAD=1` und `VALID_IN=1`
gesetzt, `CLK` durch den Simulator-Takt und
`DATAPATH_STARTUP_RESET` durch `PowerOnReset` ersetzt. Der negative
Akkumulatorstatus diente in der temporären Kopie als Haltsignal:

```bash
timeout 20s /root/.local/share/mise/installs/java/21.0.2/bin/java \
  -jar .venv/Include/logisim-evolution-4.1.0-all.jar \
  -tty table,halt /tmp/ap195-datapath.circ
```

Die ignorierten Rohdaten liegen unter `artifacts/ap19.5-operations/`. Ihre
SHA-256-Digests sind:

```text
936a200a548095839f50eb66c6f738367dc38a95381bd47db9c2b30be53d8455  raw-results.json
681ab5d0bb884435a8a1f4781b2d63386bb137f6d045afc607acd4057cc4d121  comparison.json
de2f065e8b25e072911b4732466833e9d33f6d834f0dbd2cde9dc20e09f1f453  datapath-write.tsv
```

### Beobachteter Nachweis

`Datapath` startete definiert bei `ACC_OUT=0x0000` und erreichte an der
nächsten aktiven Flanke gemeinsam `ACC_OUT=0x8000`,
`ACC_VALID_OUT=1`, `ZERO=0` und `NEGATIVE=1`. Wert und Validität werden im
isolierten Akkumulator somit an derselben vorgesehenen Flanke geschrieben.

Im kombinatorischen Operationsblatt stimmten dagegen nur **12 von 20**
gezielten Fällen vollständig mit dem VM-Vertrag überein. Erfolgreich waren
Konstantladen einschließlich Null und `0x8000`, gültiges `NOT`, normale
Addition, Subtraktion und Multiplikation, Additions- und
Subtraktionsüberlauf sowie `AND`, `OR` und `XOR`. Dabei blieben die Ausgänge
der jeweils inaktiven Rechenfamilien neutral genug, um das ausgewählte
Ergebnis nicht zu überschreiben.

Die acht Abweichungen lassen sich bereits an den benannten Ausgängen des
isolierten Blatts beobachten:

| Fall | Erwartung | Elektrisch |
|---|---|---|
| Speicherladen, gültig | `0x1234`, valid | `0x0000`, valid |
| Speicherladen, ungültig | `0x0000`, invalid + `INVALID_OPERAND` | `0x0000`, valid |
| `NOT` bei ungültigem ACC | neutrales Ergebnis, invalid + Fehler | `0xffff`, invalid + Fehler |
| `0x4000 * 2` | `0x8000`, `OVERFLOW=1` | `0x8000`, `OVERFLOW=0` |
| `-7 / 2` | `-3` (`0xfffd`), valid | `-4` (`0xfffc`), valid + `DIVIDE_BY_ZERO` |
| `7 / 0` | invalid + `DIVIDE_BY_ZERO` | unverändert `7`, valid, kein Fehler |
| `XOR` bei ungültigem ACC | neutrales Ergebnis, invalid + Fehler | `0x55aa`, invalid + Fehler |
| Speicher-`ADD` bei ungültigem Wert | neutrales Ergebnis, invalid + Fehler | unverändert `5`, valid |

Der erste Operations-Unterschied liegt damit in der Wahl des Speicherwerts:
Schon ein reines Speicherladen erreicht nicht `RESULT_VALUE`. Unabhängig
davon sind weitere lokale Fehler nachgewiesen: Multiplikationsüberlauf wird
nicht gemeldet, und der Divisionspfad rundet anders als die VM und wertet die
Nullteilerbedingung ersichtlich falsch aus. Diese Befunde sind keine Folge der
alten Opcode-Belegung, da der Decoder bei diesem isolierten Lauf nicht
beteiligt war.

Das vollständige Abnahmekriterium von 19.5 besteht folglich nicht. Die Aufgabe
ist als Diagnose mit Abweichung abgeschlossen; gemäß Stop-Regel werden weder
diese späteren Operationsfehler noch der Decoder vor 19.8 repariert.

### Offene Risiken und Übergabe an 19.6

- Die 20 Fälle isolieren `Operations` und `Datapath`, sind aber wegen des
  bekannten Decoderfehlers noch keine durch Maschinenwörter ausgelösten
  Ende-zu-Ende-ROM-Läufe. Diese folgen nach der minimalen Reparatur in 19.8.
- Ein einzelner Akkumulatorlauf belegt die gekoppelte Schreibflanke, aber noch
  nicht alle Write-Enable-Kombinationen im integrierten Top-Level. Dessen
  inaktive Zweige werden in der Regression nach Reparatur erneut geprüft.
- Erneut kam Java 21.0.2 statt Temurin 21.0.8 zum Einsatz; die gepinnte
  Logisim-Version war 4.1.0. Die finale Abnahme bleibt 19.9 vorbehalten.
- 19.6 untersucht nun zuerst den direkten Speicherpfad, weil dessen Wert und
  Validität schon am Eingang von `Operations` falsch ausgewählt werden
  könnten. Reparaturen bleiben weiterhin bis 19.8 ausgesetzt.

## 19.6 Adresspfad und Speicher debuggen

### Ausgangslage

Wegen der bekannten Opcode-Abweichung aus 19.4 wurden `AddressPath`,
`EffectiveAddress` und `Memory` erneut direkt über ihre benannten Pins
angeregt. So ließen sich Adressregister, Auswahl und RAM von Decoder und
Operationsblatt trennen. Geprüft wurden Direktadresse, Adressregister und
Register-plus-Offset, die Grenze `0x0fff`, ein Wert außerhalb des bestückten
Speichers sowie gültige und ungültige Schreibdaten. Die eingecheckte Schaltung
blieb unverändert.

### Kommando oder Bedienfolge

Ein lokales Python-Skript erzeugte temporäre Projektkopien, setzte jeweils nur
die Eingabepins der drei vorhandenen Unterblätter auf Konstanten und ersetzte
Takt und Startreset für die synchronen Versuche durch `Clock` und
`PowerOnReset`. Die Ausgänge wurden mit Logisim-evolution 4.1.0 tabellarisch
aufgenommen:

```bash
PYTHONPATH=src python3 /tmp/ap196.py

/root/.local/share/mise/installs/java/21.0.2/bin/java \
  -jar .venv/Include/logisim-evolution-4.1.0-all.jar \
  -tty table /tmp/ap196-EFFECTIVE-CASE.circ

/root/.local/share/mise/installs/java/21.0.2/bin/java \
  -jar .venv/Include/logisim-evolution-4.1.0-all.jar \
  -tty table,halt /tmp/ap196-SEQUENTIAL-CASE.circ
```

Für die synchronen Kopien diente ausschließlich ein temporärer Ausgang als
Haltebedingung. Die ignorierten Rohdaten liegen unter
`artifacts/ap19.6-address-memory/`. Repräsentative SHA-256-Digests sind:

```text
a49d49e2c9dd6310ba0c575bf4f0978299d2f1c078554deb5ad08c681d495887  address-path.tsv
ef05ea7d01416e5cfbae9609b3aa0702e4802191a91ea04c9cea470efcd2f996  address-path-carry.tsv
629a2cc094f5233a2e6fd124767ca5d8bad4270795b3becefa7aa8bc0404326f  memvalid.tsv
b08ad4ce46b9713ba4f0620353760a23ad97424a28f081673a257472e388cb3f  meminvalid.tsv
```

### Beobachteter Nachweis

`AddressPath` startete definiert bei Adresse 0 mit ungültigem Register. An der
nächsten aktiven Flanke wurden Adresse 20 und ihr Validitätsbit gemeinsam
übernommen; der Offset 1 ergab Adresse 21 ohne Carry. Der Grenzfall
`0xffff + 1` ergab `0x0000` und `OFFSET_CARRY=1`. Damit sind Registerwert,
Registervalidität und der 16-Bit-Addierer im isolierten Blatt konsistent.

Auch die beiden RAMs teilen im isolierten `Memory`-Blatt tatsächlich Adresse,
Write-Enable und Takt. Ein gültiger Schreibzugriff auf Adresse 20 lieferte nach
derselben Flanke `MEMORY_DATA=0x1234` und `MEMORY_VALID=1`; ein ungültiger
Schreibzugriff auf Adresse 21 lieferte gekoppelt `0x5678` und
`MEMORY_VALID=0`. Ein Speicher-Schreibzugriff veränderte in diesen isolierten
Versuchen keinen Akkumulator, weil `Memory` keine Verbindung zu dessen
Write-Enable besitzt. Der integrierte Nachweis für `STORE` bleibt wegen des
vorgelagerten Decoders bis zur Reparatur offen.

`EffectiveAddress` wich dagegen in allen drei Auswahlarten ab. Sein erster
Multiplexer exportierte Direktadresse beziehungsweise Adressregister und das
zugehörige Modussignal korrekt. Der zweite Multiplexer verwendete jedoch bei
inaktivem `ADDR_REG_OFFS_ARGUMENT` die Offsetadresse und bei aktivem Signal die
zuvor gewählte Direkt-/Registeradresse – genau umgekehrt zum Vertrag. So wurde
im Direktfall statt Adresse 10 die Offsetadresse 21 ausgegeben, im
Registerfall ebenfalls 21 statt 20 und im Offsetfall 20 statt 21.

Die Bereichsprüfung ist an den Ausgang dieses falsch gepolten Multiplexers
gekoppelt. Bei ausgewähltem Registerwert `0x0fff` oder `0x1000` prüfte sie
deshalb in den Versuchen die inaktive Offsetadresse 0 und meldete in beiden
Fällen `ADDRESS_OUT_OF_RANGE=0`. Die Grenzentscheidung selbst ist damit noch
nicht als defekter Vergleicher belegt; nachgewiesen ist der erste lokale
Übergang am zweiten Auswahlmultiplexer. Das vollständige Abnahmekriterium von
19.6 besteht folglich nicht, und die Reparatur bleibt Aufgabe 19.8 vorbehalten.

### Offene Risiken und Übergabe an 19.7

- Die RAM-Versuche belegen gekoppelte Einzelzugriffe, aber wegen des bekannten
  Decoders noch keine vollständigen Schreib-/Leseprogramme als Maschinenwörter.
- Ob der Bereichsvergleicher nach Korrektur der Auswahl exakt bei `0x0fff`
  trennt, muss der fokussierte Regressionstest in 19.8 erneut elektrisch
  belegen.
- Die Versuche verwendeten Java 21.0.2 statt Temurin 21.0.8. Die gepinnte
  Logisim-Version war 4.1.0; die vollständig gepinnte Abnahme bleibt 19.9.
- Aufgabe 19.7 untersucht nun Sprünge, beide Ausgabekanäle, Normal- und
  Fehlerhalt sowie alle Sticky-Flags weiterhin ohne vorgezogene Reparatur.

## 19.7 Sprünge, Ausgabe, Halt und Fehlerflags prüfen

### Ausgangslage

Die integrierten Maschinenwort-Fixtures können wegen der in 19.3 bis 19.6
bereits nachgewiesenen vorgelagerten Fehler noch nicht als isoliertes Urteil
über Kontrollfluss und Endpunkte dienen. Deshalb wurde zuerst die Topologie
zwischen den **benannten** Decoder-, Fetch- und Top-Level-Ports verfolgt und
anschließend `ErrorFlags` direkt elektrisch angeregt. Als Soll dienten die
bereits versionierten Fälle der elektrischen Matrix: alle sechs Sprünge,
genommen und nicht genommen, `PRINT`, `PRINT_ADDRESS`, beide Haltarten,
`CLEAR_ERROR` und je ein Fixture für jedes der sechs Fehlerbits. Die
eingecheckte Schaltung blieb unverändert.

### Kommando oder Bedienfolge

Ein XML-Topologielauf bildete aus allen `wire`-Endpunkten von `TinyCPUMain`
zusammenhängende Netze und ordnete die benannten Pins und Monitor-Probes zu.
Insbesondere wurden die sechs Sprungausgänge von `FetchDecodeControls`, die
vier beobachtbaren Steuerendpunkte sowie Wert- und Validitätsausgänge der
beiden Druckpfade geprüft:

```bash
python3 - <<'PY'
import collections
import xml.etree.ElementTree as ET

root = ET.parse("hardware/logisim/TinyCPU.circ").getroot()
top = next(c for c in root.findall("circuit") if c.get("name") == "TinyCPUMain")
graph = collections.defaultdict(set)
for wire in top.findall("wire"):
    a, b = wire.get("from"), wire.get("to")
    graph[a].add(b)
    graph[b].add(a)
for start in ("(3350,1070)", "(3350,1090)", "(3350,1110)", "(3350,1130)",
              "(1270,1210)", "(1270,1230)", "(1270,1270)",
              "(1270,1290)", "(1270,1310)"):
    seen, pending = {start}, [start]
    while pending:
        point = pending.pop()
        for neighbor in graph[point] - seen:
            seen.add(neighbor)
            pending.append(neighbor)
    print(start, sorted(seen))
PY
```

Für den sequentiellen Fehlerflag-Test wurde nur eine temporäre Kopie des
vorhandenen Diagnoseblatts erzeugt. `CLK` wurde durch den Simulator-Takt und
der Startreset durch `PowerOnReset` ersetzt. Alle sechs `SET_*`-Eingänge und
`CLEAR_ERROR` lagen gleichzeitig auf 1; damit prüft die erste aktive Flanke
unmittelbar die geforderte Set-vor-Clear-Priorität:

```bash
python3 /tmp/ap197_flags.py
timeout 20s /root/.local/share/mise/installs/java/21.0.2/bin/java \
  -jar .venv/Include/logisim-evolution-4.1.0-all.jar \
  -tty table,halt /tmp/ap19.7-error-flags.circ \
  > artifacts/ap19.7-control-endpoints/error-flags-set-before-clear.tsv
```

Die lokale Rohdatei bleibt wie die bisherigen Simulatorartefakte außerhalb
von Git. Ihr SHA-256-Digest ist:

```text
bb152dd6b1dab51cc5e2c4401dadc87adb31a4e425db393e5c7a11068c1b15ff  error-flags-set-before-clear.tsv
```

### Beobachteter Nachweis

Die Sprungsteuerung ist nicht vollständig bis zum PC geführt. Nur
`JUMP_NOT_ZERO` besitzt in `FetchDecode` mit `JNZ_TAKEN` einen bedingten
PC-Auswahlpfad. `JUMP_ADR`, `JUMP_ZERO`, `JUMP_NEGATIVE`, `JUMP_ERROR` und
`JUMP_NOT_ERROR` verlassen `FetchDecodeControls` auf `TinyCPUMain` jeweils nur
über eine kurze Leitung zu ihrem gleichnamigen `MONITOR_*`-Probe. Diese fünf
Netze besitzen keinen weiteren Verbraucher und erreichen insbesondere weder
PC-Register noch PC-Multiplexer. Damit können die vorhandenen Taken-Fixtures
dieser fünf Sprünge elektrisch nicht zum Sprungziel gelangen; ihre
Not-taken-Varianten unterscheiden sich am PC mangels angeschlossenem
Bedingungspfad nicht von ihnen. Beim allein angeschlossenen `JUMP_NOT_ZERO`
bilden `DEC_JUMP_NOT_ZERO`, `NOT_ZERO` und das UND-Gatter die Bedingung zwar
korrekt, der integrierte Maschinenwortlauf bleibt aber durch Decoder- und
Fetch-Abweichungen aus 19.3/19.4 blockiert.

Noch früher und unabhängig vom Decoder ist die Abweichung an den Endpunkten:
`PRINT_ENABLE`, `PRINT_ADDRESS_ENABLE`, `HALTED` und `HALTED_WITH_ERROR` sind
vier isolierte Top-Level-Pins. An keinem ihrer Anschlusskoordinaten beginnt
oder endet eine Leitung. Deshalb können weder die zwei Druck-Enable-Signale
noch Normal- oder Fehlerhalt beobachtbar werden. Dies erklärt auch, warum der
Minimalversuch aus 19.3 trotz temporärer ROM-Belegung den Tabellenmodus nicht
per Halt beenden konnte. Die Datenendpunkte sind davon getrennt: `PRINT_VALUE`
ist mit dem Akkumulatorwert verbunden, und `PRINT_ADDRESS_VALUE` sowie
`PRINT_ADDRESS_VALID` sind mit dem Speicherpfad verbunden. `PRINT_VALID`
erreicht ebenfalls ein Datapath-Netz. Damit liegt kein Kurzschluss zwischen
Steuer- und Datennetzen vor, sondern es fehlen die vier Steuerverbindungen.

Das isolierte `ErrorFlags`-Blatt startete mit sechs Nullen. An der ersten
aktiven Flanke wurden bei gleichzeitigem `SET_*=1` und `CLEAR_ERROR=1` alle
sechs Ausgänge 1; der als Haltepin verwendete `OVF_OUT` und die fünf
Tabellenspalten belegen gemeinsam alle Flags. Die Schaltung realisiert für
jedes Bit dieselbe Gleichung `SET_* OR (alter_Wert AND NOT CLEAR_ERROR)`.
Dadurch ist das Setzen dominant, ein gesetztes Bit bleibt ohne Clear erhalten,
und `CLEAR_ERROR` löscht bei inaktivem Set alle sechs Register gemeinsam.
Zwischen den sechs Ausgängen besteht kein fremdes Fehlernetz. Die isolierte
Flagbank erfüllt somit den Sticky-Vertrag; ihre Ende-zu-Ende-Anregung durch
Maschinenprogramme bleibt bis zu den vorgelagerten Reparaturen offen.

Das vollständige Abnahmekriterium von 19.7 besteht wegen der unverdrahteten
Sprünge und Endpunkte nicht. Die Aufgabe ist als Diagnose mit Abweichung
abgeschlossen; entsprechend der Stop-Regel wurde noch keine Leitung ergänzt.

### Offene Risiken und Übergabe an 19.8

- Die fünf fehlenden Sprungpfade benötigen neben den Decoderleitungen auch die
  jeweils fachlich richtige Bedingung und eine gemeinsame PC-Zielauswahl. Sie
  dürfen nicht nur an den bestehenden `JUMP_NOT_ZERO`-Pfad kurzgeschlossen
  werden.
- Die vier isolierten Top-Level-Steuerpins müssen in 19.8 zu den jeweils
  benannten Decoder-/Fetch-Signalen geführt werden. Wert- und Validitätsnetze
  der Druckpfade dürfen dabei nicht umverdrahtet werden.
- Der elektrische Prioritätslauf belegt alle sechs Flags gemeinsam und die
  Blattgleichungen belegen ihr Halten und Löschen. Separate Ende-zu-Ende-ROMs
  für jedes Fehlerbit folgen nach der Reparatur der vorgelagerten Pfade.
- Der Lauf nutzte Java 21.0.2 statt Temurin 21.0.8; die gepinnte
  Logisim-evolution-Version war 4.1.0. Die finale Umgebung bleibt Aufgabe
  19.9.
- Aufgabe 19.8 beginnt gemäß Stop-Regel nicht mit diesen späteren Befunden,
  sondern mit dem ersten bereits in 19.3 belegten Unterschied
  `Konstante → FetchDecode.PROGRAM_LIMIT`. Erst nach dessen fokussierter
  Regression wird der nächste erste Unterschied repariert.

## 19.8 Ersten abweichenden Netzübergang minimal reparieren

### Ausgangslage

Der früheste belegte Unterschied aus 19.3 lag vor Takt 0: Eine 16-Bit-Konstante
ohne expliziten Wert trieb `FetchDecode.PROGRAM_LIMIT` mit 0, während das
unveränderte 16/12-Profil als höchste Programmadresse `0x0fff` festlegt. Die
weiteren Befunde aus 19.4 bis 19.7 wurden für diese erste Korrektur bewusst
nicht mitbearbeitet.

### Kommando oder Bedienfolge

Vor der Schaltungsänderung wurde ein topologischer Regressionstest ergänzt.
Er sucht die Quelle über ihren fachlichen Namen statt über eine historische
Canvas-Koordinate, prüft Breite und Wert und stellt sicher, dass sie
ausschließlich das bereits vorhandene Fetch-Netz treibt. Auf dem
Ausgangsstand scheiterte diese Prüfung, weil keine benannte Quelle mit dem
Profilmaximum existierte. Anschließend wurden an der vorhandenen Konstante nur
der Name `PROGRAM_LIMIT_MAX` und der Wert `0xfff` ergänzt. Die fokussierte
Abnahme lautete:

```bash
python3 -m unittest \
  tests.test_tiny_cpu_logisim.LogisimLauncherTests.test_program_limit_source_uses_profile_maximum
timeout 30s java -jar .venv/Include/logisim-evolution-4.1.0-all.jar \
  -tty stats hardware/logisim/TinyCPU.circ
scripts/test-offline.sh
```

### Beobachteter Nachweis

Der neue Regressionstest besteht und findet genau eine 16 Bit breite,
`PROGRAM_LIMIT_MAX` benannte Quelle mit dem Wert `0xfff` sowie genau eine
angeschlossene Leitung. Logisim-evolution 4.1.0 lädt das geänderte Gesamtprojekt
weiterhin mit Exitcode 0. Damit ist der Übergang
`Konstante → FetchDecode.PROGRAM_LIMIT` minimal korrigiert, ohne einen
zusätzlichen Treiber, eine neue Leitung oder eine Änderung am Fetch-Unterblatt
einzuführen.

Die Offline-Suite prüft die geänderte Datei strukturell erfolgreich. Ihre zwei
bereits in 19.1 dokumentierten, koordinatengebundenen Altprüfungen für
`ADD_OPERAND` und `SUB_OPERAND` schlagen unverändert fehl. Sie sind weder eine
Regression dieser Änderung noch ein Abnahmenachweis für den benannten
Programmgrenzpfad.

### Zweite Reparatur: Decoder-Steuerfläche

Vor der zweiten Schaltungsänderung wurde `scripts/test-logisim-decode.py` als
fokussierte elektrische Regression ergänzt. Das Skript wählt in einer
temporären Projektkopie `FetchDecodeControls` als Startblatt, lässt
Logisim-evolution alle 64 Eingabekombinationen tabellieren und leitet die
Sollzeile unmittelbar aus `tinycpu-machine-v1.json` ab. Der Ausgangsstand
scheiterte bereits bei Opcode 0, weil er `ADD_OPERAND` statt `LOAD_OPERAND`
setzte.

Die Decoder-Ausgänge wurden anschließend ausschließlich innerhalb von
`FetchDecodeControls` neu zugeordnet. Benannte Tunnel `DECODE_00` bis
`DECODE_63` verbinden jeden Ausgang des 6-zu-64-Decoders mit den fachlich
passenden Operations-, Argument- und Direktsignalen. Selektoren mit mehr als
acht Quellen sind in zwei begrenzte OR-Bänke und einen definiert geerdeten
Kombinierer geteilt. Dadurch bleiben alle Eingänge definiert; insbesondere
führen die Codes 50 bis 63 gemeinsam auf `INVALID_OPERAND`, während die sechs
laufzeitabhängigen `SET_*`-Ausgänge beim reinen Opcode-Decode null bleiben.

Die fokussierte Abnahme lautet:

```bash
LOGISIM_JAR=.venv/Include/logisim-evolution-4.1.0-all.jar \
  scripts/test-logisim-decode.py
python3 src/tiny_cpu_verify.py
timeout 30s java -jar .venv/Include/logisim-evolution-4.1.0-all.jar \
  -tty stats hardware/logisim/TinyCPU.circ
scripts/test-offline.sh
```

Der elektrische Test besteht mit **50 gültigen Opcodes und 14 reservierten
Codes**. Alle 64 Zeilen und alle 33 benannten Ausgänge stimmen mit dem
Maschinenvertrag überein; es treten keine `E`- oder schwebenden Werte auf. Die
Strukturprüfung und die Projektladung bestehen ebenfalls. Die Offline-Suite
endet weiterhin ausschließlich mit den zwei seit 19.1 bekannten,
koordinatengebundenen Altprüfungen für `ADD_OPERAND` und `SUB_OPERAND`.

### Dritte Reparatur: Speicher-/Direktoperandwahl

Der erste Rechenpfadunterschied aus 19.5 entstand vor den einzelnen
Operationszweigen: Der Datenmultiplexer wurde fälschlich von der bereits
berechneten Operandengültigkeit ausgewählt, und der inaktive Ergebniszweig
führte unabhängig von der Auswahl stets `IMMEDIATE_VALUE` sowie eine konstante
Gültigkeit. Dadurch konnte ein gültiger Speicherwert das Blatt nicht als
`RESULT_VALUE` verlassen.

Die vorhandenen Multiplexer werden nun beide direkt von `CONST_OPERAND`
gesteuert. Ihre Daten- und Gültigkeitsausgänge sind über die benannten Netze
`SELECTED_OPERAND_VALUE` und `SELECTED_OPERAND_VALID` sowohl mit den
Operationszweigen als auch mit dem inaktiven Ergebniszweig verbunden. Bei
einem Direktoperanden ist dessen Gültigkeit definitionsgemäß eins, bei einem
Speicheroperanden stammt sie weiterhin von `MEMORY_VALID`. Es wurde kein
Operationszweig und keine ISA-Semantik geändert.

Die neue elektrische Regression ersetzt in einer temporären Projektkopie nur
die benannten Eingabepins von `Operations` durch Konstanten. Vor der Reparatur
lieferte der Speicherfall `0xabcd` statt `0x1234`; danach bestehen Speicher-
und Direktfall mit parallel ausgewählter Gültigkeit:

```bash
LOGISIM_JAR=.venv/Include/logisim-evolution-4.1.0-all.jar \
  scripts/test-logisim-operations.py
python3 src/tiny_cpu_verify.py
timeout 30s java -jar .venv/Include/logisim-evolution-4.1.0-all.jar \
  -tty stats hardware/logisim/TinyCPU.circ
scripts/test-offline.sh
```

Die fokussierte elektrische Abnahme, die Strukturprüfung und das Laden des
Gesamtprojekts bestehen. Die Offline-Suite endet weiterhin nur mit den zwei
seit 19.1 bekannten koordinatengebundenen ADD-/SUB-Altprüfungen. Die weiteren
in 19.5 isolierten Abweichungen wurden gemäß Stop-Regel nicht vorgezogen.

### Vierte Reparatur: Multiplikationsüberlauf

Der nächste Fall aus 19.5, `0x4000 * 2`, lieferte zwar das gekürzte Ergebnis
`0x8000`, setzte aber `OVERFLOW` nicht. Das vorhandene Blatt verglich bereits
die beiden Operandenvorzeichen und das Ergebnisvorzeichen, verknüpfte die
beiden Abweichungen jedoch mit AND. Bei zwei positiven Operanden war der erste
Term damit stets null und unterdrückte gerade den beobachteten positiven
Überlauf.

Der Ausgang vergleicht nun per XOR das erwartete Produktvorzeichen
`left_sign XOR right_sign` direkt mit dem tatsächlichen Ergebnisvorzeichen.
Die unnötige Zwischenstufe `left_sign XOR result_sign` wurde aus diesem Pfad
entfernt; Ergebnisbus, Multiplikator und die übrigen Operationszweige blieben
unverändert. Die elektrische Operationsregression enthält jetzt zusätzlich
den zuvor fehlschlagenden Grenzfall und eine nicht überlaufende Multiplikation:

```bash
LOGISIM_JAR=.venv/Include/logisim-evolution-4.1.0-all.jar \
  scripts/test-logisim-operations.py
python3 src/tiny_cpu_verify.py
timeout 30s java -jar .venv/Include/logisim-evolution-4.1.0-all.jar \
  -tty stats hardware/logisim/TinyCPU.circ
scripts/test-offline.sh
```

Der fokussierte Lauf meldet für `0x4000 * 2` jetzt `RESULT_VALUE=0x8000` und
`OVERFLOW=1`; `3 * 2` bleibt bei `0x0006` mit `OVERFLOW=0`. Strukturprüfung
und Projektladung bestehen ebenfalls. Die beiden koordinatengebundenen
ADD-/SUB-Altprüfungen bleiben von dieser lokalen Korrektur unberührt.

### Offene Risiken und nächster Übergang

### Fünfte Reparatur: Division-durch-null-Erkennung

Der nächste Rechenpfadunterschied lag im `DivArithmeticCircuit`: Der vorhandene
Vergleicher erzeugte das Signal „Divisor größer als null“, dieses war jedoch
direkt mit dem Fehlersignal und nach der Invertierung mit der
Gültigkeitsfreigabe verbunden. Bei einem positiven Divisor wurde deshalb
fälschlich `DIVIDE_BY_ZERO=1` gemeldet, während ein Divisor von null das
Ergebnis als gültig passieren ließ.

Das Nichtnullsignal erreicht nun direkt die Gültigkeitsfreigabe; erst seine
Invertierung treibt `DIVIDE_BY_ZERO`. Der Vergleicher erhält unverändert den
ausgewählten Divisor und die 16-Bit-Nullkonstante; Ergebnisbus, Divider und
Aktivierungsmultiplexer wurden nicht verändert. Die elektrische
Operationsregression prüft jetzt sowohl
`7 / 2` als auch `7 / 0`. Der erste Fall liefert `0x0003`, bleibt gültig und
setzt keinen Fehler; der zweite setzt nun `DIVIDE_BY_ZERO`. Das isolierte
Divisionsblatt macht dabei sein Ergebnis ungültig. Am zusammengeführten
`Operations.RESULT_IS_VALID` wird diese Null jedoch noch von den
Gültigkeitsausgängen inaktiver Operationszweige überdeckt; das ist gemäß
Stop-Regel der nächste zu reparierende Netzübergang und wird von dieser
lokalen Fehlerleitungsreparatur noch nicht verdeckt.

Beim aktuellen manuellen Redraw war außerdem nur die stabile Beschriftung der
unverändert korrekt dimensionierten und belegten Programmgrenzen-Konstante
verloren gegangen. `PROGRAM_LIMIT_MAX` wurde deshalb wiederhergestellt, damit
die bereits vorhandene topologische Regression die Quelle weiterhin ohne
Canvas-Koordinate identifizieren kann.

### Sechste Reparatur: aktivierungsgebundene Ergebnisgültigkeit

Der nächste Unterschied lag am Übergang vom Divisionsblatt zum gemeinsamen
`Operations.RESULT_IS_VALID`: `DivArithmeticCircuit.RESULT_VALID` wurde nur
aus Eingabegültigkeit und Nichtnullprüfung gebildet. Daher lieferte der
inaktive Divisionszweig bei einem beliebigen Nichtnulloperanden weiterhin eine
Eins an das gemeinsame ODER; bei einer aktiven Division durch null wurde
umgekehrt deren Null von den inaktiven Zweigen überdeckt.

Die vorhandenen `RANGE_VALID`-UND-Gatter der vier arithmetischen Zweige
verknüpfen nun zusätzlich das jeweilige `*_ACTIVATED`-Signal. Damit sind ihre
Gültigkeitsausgänge im inaktiven Zustand neutral; eine aktive Division ist nur
mit gültiger Eingabe und einem Divisor ungleich null gültig. Die Regression
verlangt für `7 / 0` jetzt ausdrücklich `RESULT_IS_VALID=0`; vor der Änderung
lieferte dieser Fall 1. Ergebnisbusse, Rechenbausteine und Fehlerausgänge
wurden nicht verändert.

Die fokussierte Abnahme lautet:

```bash
LOGISIM_JAR=.venv/Include/logisim-evolution-4.1.0-all.jar \
  scripts/test-logisim-operations.py
python3 -m unittest \
  tests.test_tiny_cpu_logisim.LogisimLauncherTests.test_program_limit_source_uses_profile_maximum
timeout 30s java -jar .venv/Include/logisim-evolution-4.1.0-all.jar \
  -tty stats hardware/logisim/TinyCPU.circ
```

- Die bisherigen Reparaturen schließen 19.8 noch nicht ab. Der
  `DIVIDE_BY_ZERO`-Ausgang wird bei Divisor null weiterhin auch dann gesetzt,
  wenn `DIV_OPERAND=0` ist; seine Aktivierung ist gemäß Stop-Regel der nächste
  belegte Rechenpfadunterschied.
- Der integrierte Minimal- und Matrixlauf bleibt zusätzlich durch die später
  diagnostizierten Adress-, Sprung- und Haltepfade blockiert. Diese werden
  nicht in dieselbe Änderung vorgezogen.
- Die vollständige elektrische Matrix und die gepinnte Java-Umgebung bleiben
  weiterhin der Abnahme in 19.9 vorbehalten.

### Siebte Reparatur: aktivierungsgebundener Divisionsfehler

Der nächste belegte Unterschied lag am Ausgang `DIVIDE_BY_ZERO` des
`DivArithmeticCircuit`: Das invertierte Nichtnullsignal erreichte den Ausgang
unabhängig von `DIV_ACTIVATED`. Deshalb meldete bereits ein inaktiver
Divisionszweig mit einem zufällig ausgewählten Nulloperanden einen
Divisionsfehler.

Ein neues UND-Gatter verknüpft das vorhandene Nullsignal unmittelbar vor dem
Ausgang mit `DIV_ACTIVATED`. Die Nichtnullprüfung, Ergebnisberechnung und
Gültigkeitslogik bleiben unverändert. Die elektrische Operationsregression
enthält nun zusätzlich den zuvor fehlschlagenden Fall mit Nulloperand und
`DIV_OPERAND=0`; er setzt `DIVIDE_BY_ZERO` nicht mehr. Die beiden aktiven Fälle
belegen weiterhin, dass `7 / 2` keinen Fehler und `7 / 0` genau diesen Fehler
meldet.

Die fokussierte Abnahme lautet:

```bash
LOGISIM_JAR=.venv/Include/logisim-evolution-4.1.0-all.jar \
  scripts/test-logisim-operations.py
python3 src/tiny_cpu_verify.py
timeout 30s java -jar .venv/Include/logisim-evolution-4.1.0-all.jar \
  -tty stats hardware/logisim/TinyCPU.circ
scripts/test-offline.sh
```

- Die bisherigen Reparaturen schließen 19.8 noch nicht ab. Der in 19.5
  dokumentierte Unterschied bei der Rundung vorzeichenbehafteter Division ist
  gemäß Stop-Regel der nächste zu untersuchende Rechenpfadübergang.
- Der integrierte Minimal- und Matrixlauf bleibt zusätzlich durch die später
  diagnostizierten Adress-, Sprung- und Haltepfade blockiert. Diese werden
  nicht in dieselbe Änderung vorgezogen.
- Die vollständige elektrische Matrix und die gepinnte Java-Umgebung bleiben
  weiterhin der Abnahme in 19.9 vorbehalten.

### Achte Reparatur: vorzeichenbehaftete Division mit Rundung zu null

Der nächste belegte Unterschied lag am Divider des `DivArithmeticCircuit`:
Obwohl dessen oberer Dividendeneingang bereits die Vorzeichenerweiterung des
linken Operanden erhielt, verwendete der Baustein weiterhin seinen
vorzeichenlosen Standardmodus. Für `-7 / 2` entstand dadurch im unteren
Ergebniswort `-4` statt der vom VM-Vertrag verlangten, zu null gerundeten
`-3`.

Der vorhandene Divider ist nun explizit auf Zweierkomplement gestellt. Seine
Operanden, Vorzeichenerweiterung, Nullprüfung sowie Ergebnis- und
Gültigkeitsleitungen bleiben unverändert. Die elektrische
Operationsregression enthält neben `7 / 2` jetzt den zuvor fehlschlagenden Fall
`-7 / 2`; er liefert `-3`, bleibt gültig und setzt keinen Divisionsfehler.
Damit deckt der Test genau den zuvor abweichenden Übergang am benannten
Divisionsbaustein ab.

Die fokussierte Abnahme lautet:

```bash
LOGISIM_JAR=.venv/Include/logisim-evolution-4.1.0-all.jar \
  scripts/test-logisim-operations.py
python3 src/tiny_cpu_verify.py
timeout 30s java -jar .venv/Include/logisim-evolution-4.1.0-all.jar \
  -tty stats hardware/logisim/TinyCPU.circ
scripts/test-offline.sh
```

- Die bisherigen Reparaturen schließen 19.8 noch nicht ab. Der integrierte
  Minimal- und Matrixlauf bleibt durch die bereits diagnostizierten Adress-,
  Sprung- und Haltepfade blockiert; gemäß Stop-Regel wird als Nächstes wieder
  der erste dort sichtbare Netzübergang untersucht.
- Die vollständige elektrische Matrix und die gepinnte Java-Umgebung bleiben
  weiterhin der Abnahme in 19.9 vorbehalten.

### Neunte Reparatur: Auswahl der effektiven Adresse

Der nächste bereits in 19.6 belegte Unterschied lag am zweiten Multiplexer des
Blatts `EffectiveAddress`. Seine Eingänge waren gegenüber dem Steuersignal
`ADDR_REG_OFFS_ARGUMENT` vertauscht: Ohne Offset wurde `OFFSET_ADDR` gewählt,
mit Offset dagegen die zuvor ausgewählte Direkt- oder Registeradresse. Da auch
die Bereichsprüfung vom Multiplexerausgang gespeist wird, prüfte sie dadurch
dieselbe falsche Adresse.

Die beiden vorhandenen 16-Bit-Eingangsnetze wurden unmittelbar vor dem
Multiplexer getauscht. Bei Steuersignal 0 liegt nun `REG_SELECTED`, bei 1
`OFFSET_ADDR` an; Multiplexer, Steuernetz, Ausgang und Bereichsvergleicher
bleiben unverändert. Die neue elektrische Regression regt das Blatt nur über
seine benannten Pins an und prüft Direkt-, Register- und Offsetmodus sowie die
Profilgrenze `0x0fff` und die erste unzulässige Adresse `0x1000`. Vor der
Reparatur scheiterte bereits der Direktfall; danach bestehen alle fünf Fälle.

Die fokussierte Abnahme lautet:

```bash
LOGISIM_JAR=.venv/Include/logisim-evolution-4.1.0-all.jar \
  scripts/test-logisim-effective-address.py
python3 src/tiny_cpu_verify.py
timeout 30s java -jar .venv/Include/logisim-evolution-4.1.0-all.jar \
  -tty stats hardware/logisim/TinyCPU.circ
scripts/test-offline.sh
```

- Die bisherigen Reparaturen schließen 19.8 noch nicht ab. Der nächste
  integrierte Lauf muss nun den ersten Unterschied hinter dem korrigierten
  Adresspfad bestimmen; Sprung-, Ausgabe- und Haltepfade werden nicht
  vorgezogen.
- Die vollständige elektrische Matrix und die gepinnte Java-Umgebung bleiben
  weiterhin der Abnahme in 19.9 vorbehalten.

### Nachprüfung der topologischen Regressionen

Die Nachprüfung der vollständigen Offline-Suite zeigte, dass die drei dort
verbliebenen Fehler keine fehlenden ADD-/SUB-Leitungen belegten. Beide
Top-Level-Verbindungen vom aktuellen `FetchDecodeControls` zum aktuellen
`Operations` waren bereits vorhanden. Die internen Tests erwarteten jedoch
noch die Koordinaten einer überholten Anordnung des `Operations`-Blatts. Sie
ermitteln die betreffenden Komponenten jetzt über `ADD_OPERAND`, `ADD_OPERATION`,
`SUB_OPERAND` und `SUB_OPERATION` und verfolgen den tatsächlich verbundenen
Leitungspfad zwischen ihren aktuellen Ports. Damit bleibt eine echte
Unterbrechung erkennbar, ohne verschobene Symbole als Fehler zu behandeln.

An der vorhandenen Programmgrenzenkonstante mit dem unveränderten Wert `0xfff`
war dagegen beim manuellen Redraw lediglich die stabile Beschriftung verloren
gegangen. `PROGRAM_LIMIT_MAX` ist wiederhergestellt, sodass der Test die Quelle
ohne Canvas-Koordinate findet und weiterhin Breite, Wert sowie den einzelnen
angeschlossenen Fetch-Pfad prüft. Datenwert und Verdrahtung wurden dabei nicht
verändert.

### Zehnte Reparatur: Freigabe des Akkumulator-Ausgabeports

Der erste integrierte Unterschied hinter dem korrigierten Adresspfad trat beim
ersten `PRINT` des Countdown-Programms auf: `FetchDecodeControls.PRINT` wurde
korrekt dekodiert, endete auf `TinyCPUMain` aber an einem offenen Netz. Der
öffentliche Ausgang `PRINT_ENABLE` war vollständig isoliert. Wert und
Gültigkeit des Akkumulator-Ausgabepfads waren davon unabhängig bereits mit
ihren öffentlichen Pins verbunden.

Eine neue, ausschließlich orthogonale Leitung verbindet nun den
`PRINT`-Ausgang der vorhandenen Decoderinstanz direkt mit `PRINT_ENABLE`.
Decoder, Datenbus, `PRINT_VALID` und die Freigabe für die Adressausgabe bleiben
unverändert. Die topologische Regression folgt dem vollständigen Netz zwischen
dem Decoderport und dem über seinen Namen gefundenen öffentlichen Pin; sie
bindet die Leitungsführung deshalb nicht an Zwischenkoordinaten.

Die fokussierte Abnahme lautet:

```bash
python3 -m unittest \
  tests.test_tiny_cpu_logisim.LogisimLauncherTests.test_print_control_reaches_public_enable_pin
python3 src/tiny_cpu_verify.py
timeout 30s java -jar .venv/Include/logisim-evolution-4.1.0-all.jar \
  -tty stats hardware/logisim/TinyCPU.circ
scripts/test-offline.sh
```

- Die bisherigen Reparaturen schließen 19.8 noch nicht ab. Der integrierte
  Countdown-Lauf erreicht wegen des weiterhin offenen `HALTED`-Endpunkts noch
  keinen beobachtbaren Normalhalt. Gemäß Stop-Regel muss der nächste Lauf den
  ersten Unterschied nach `PRINT_ENABLE` bestimmen, bevor ein weiterer
  Steuerpfad geändert wird.
- `PRINT_ADDRESS_ENABLE`, `HALTED`, `HALTED_WITH_ERROR` und fünf Sprungpfade
  bleiben entsprechend dem Befund aus 19.7 unangetastet.
- Die vollständige elektrische Matrix und die gepinnte Java-Umgebung bleiben
  weiterhin der Abnahme in 19.9 vorbehalten.

### Elfte Reparatur: beobachtbarer Normalhalt

Der bereits hinter `PRINT_ENABLE` dokumentierte nächste Unterschied lag am
Normalhalt des Countdown-Programms. `FetchDecodeControls.HALT` wurde korrekt
dekodiert und war auf dem Top-Level bereits mit dem vorhandenen Monitornetz
verbunden, erreichte den öffentlichen Ausgang `HALTED` jedoch nicht. Damit
konnte der Tabellenlauf den fachlich erreichten Endzustand nicht beobachten.

Eine neue orthogonale Abzweigung verbindet den `HALT`-Ausgang der vorhandenen
Decoderinstanz direkt mit `HALTED`. Decoder, Monitornetz und der getrennte
Fehlerhaltpfad bleiben unverändert. Die Regression findet den öffentlichen Pin
über seinen Namen und verfolgt das vollständige Netz ab dem benannten
Decoderport, ohne Zwischenkoordinaten der Leitungsführung festzuschreiben. Vor
der Reparatur schlug dieser Test fehl; danach besteht er.

Die fokussierte Abnahme lautet:

```bash
python3 -m unittest \
  tests.test_tiny_cpu_logisim.LogisimLauncherTests.test_halt_control_reaches_public_halted_pin
python3 src/tiny_cpu_verify.py
timeout 30s java -jar .venv/Include/logisim-evolution-4.1.0-all.jar \
  -tty stats hardware/logisim/TinyCPU.circ
scripts/test-offline.sh
```

- Die bisherigen Reparaturen schließen 19.8 noch nicht ab. Gemäß Stop-Regel
  muss der nächste integrierte Lauf den ersten Unterschied nach dem nun
  beobachtbaren Normalhalt bestimmen, bevor ein weiterer Steuerpfad geändert
  wird.
- `PRINT_ADDRESS_ENABLE`, `HALTED_WITH_ERROR` und fünf Sprungpfade bleiben
  entsprechend dem Befund aus 19.7 unangetastet.
- Die vollständige elektrische Matrix und die GUI-Kurzabnahme bleiben Aufgabe
  19.9 vorbehalten.

### Zwölfte Reparatur: beobachtbarer Fehlerhalt

Der erste integrierte Unterschied nach dem beobachtbaren Normalhalt lag am
expliziten Fehlerhalt. `FetchDecodeControls.HALT_ERROR` wurde korrekt dekodiert,
endete auf `TinyCPUMain` aber weiterhin an einem offenen Monitornetz. Der
öffentliche Ausgang `HALTED_WITH_ERROR` war vollständig isoliert und konnte
das fachlich erreichte Programmende deshalb nicht an den Tabellenlogger
weitergeben.

Eine neue orthogonale Leitung verbindet den `HALT_ERROR`-Ausgang der
vorhandenen Decoderinstanz direkt mit `HALTED_WITH_ERROR`. Normalhalt,
Monitornetz und die benachbarten Ausgabe-Freigaben bleiben getrennt. Die
Regression findet den öffentlichen Pin über seinen Namen und verfolgt das
vollständige Netz ab dem benannten Decoderport; sie enthält keine Annahme über
die Zwischenkoordinaten. Vor der Reparatur schlug dieser Test fehl, danach
besteht er.

Die fokussierte Abnahme lautet:

```bash
python3 -m unittest \
  tests.test_tiny_cpu_logisim.LogisimLauncherTests.test_halt_error_control_reaches_public_halted_with_error_pin
python3 src/tiny_cpu_verify.py
timeout 30s java -jar .venv/Include/logisim-evolution-4.1.0-all.jar \
  -tty stats hardware/logisim/TinyCPU.circ
scripts/test-offline.sh
```

- Die bisherigen Reparaturen schließen 19.8 noch nicht ab. Gemäß Stop-Regel
  muss der nächste integrierte Lauf den ersten Unterschied nach dem nun
  beobachtbaren Fehlerhalt bestimmen, bevor ein weiterer Steuerpfad geändert
  wird.
- `PRINT_ADDRESS_ENABLE` und fünf Sprungpfade bleiben entsprechend dem Befund
  aus 19.7 unangetastet.
- Die vollständige elektrische Matrix und die GUI-Kurzabnahme bleiben Aufgabe
  19.9 vorbehalten.

### Dreizehnte Reparatur: Freigabe der adressierten Ausgabe

Der erste noch offene beobachtbare Endpunkt nach dem Fehlerhalt war die
Freigabe von `PRINT_ADDRESS`. Der Decoder stellte das Signal an
`FetchDecodeControls.PRINT_ADDRESS` bereit, und Wert sowie Gültigkeit kamen
bereits aus dem Speicherpfad am Top-Level an. Der öffentliche Ausgang
`PRINT_ADDRESS_ENABLE` blieb jedoch isoliert, sodass ein adressierter
Ausgabebefehl trotz korrekter Daten nicht als Ausgabe beobachtet werden konnte.

Eine neue orthogonale Abzweigung verbindet den vorhandenen Decoderpfad direkt
mit `PRINT_ADDRESS_ENABLE`. Der benachbarte Akkumulator-Ausgabepfad, beide
Haltepfade sowie Wert und Gültigkeit der adressierten Ausgabe bleiben
unverändert. Die Regression findet den öffentlichen Pin anhand seines Namens
und verfolgt das vollständige Netz vom benannten Decoderport, ohne
Zwischenkoordinaten festzuschreiben. Sie schlägt bei gezieltem Entfernen der
neuen Verbindung fehl und besteht mit der reparierten Leitung.

Die fokussierte Abnahme lautet:

```bash
python3 -m unittest \
  tests.test_tiny_cpu_logisim.LogisimLauncherTests.test_print_address_control_reaches_public_enable_pin
python3 src/tiny_cpu_verify.py
timeout 30s java -jar .venv/Include/logisim-evolution-4.1.0-all.jar \
  -tty stats hardware/logisim/TinyCPU.circ
scripts/test-offline.sh
```

- Die bisherigen Reparaturen schließen 19.8 noch nicht ab. Gemäß Stop-Regel
  muss der nächste integrierte Lauf den ersten Unterschied nach der nun
  beobachtbaren adressierten Ausgabe bestimmen.
- Die fünf Sprungpfade bleiben entsprechend dem Befund aus 19.7 unangetastet.
- Die vollständige elektrische Matrix und die GUI-Kurzabnahme bleiben Aufgabe
  19.9 vorbehalten.

### Vierzehnte Reparatur: unbedingter Sprung zum gemeinsamen PC-Auswahlpfad

Der nächste belegte Unterschied nach der adressierten Ausgabe lag am
unbedingten `JUMP_ADR`. Der Decoder führte das Signal bisher ausschließlich
zum Monitor `MONITOR_JUMP_ADR`; der PC-Multiplexer erhielt nur die Verknüpfung
für `JUMP_NOT_ZERO`. Ein Sprungziel konnte deshalb für `JUMP_ADR` nie ausgewählt
werden.

Zwei benannte ODER-Stufen bilden nun am Top-Level die logisch äquivalente
gemeinsame Taken-Bedingung
`JUMP_ADR OR (JUMP_NOT_ZERO AND NOT_ZERO)`: Die erste Stufe führt beide
Steuersignale zusammen, die zweite setzt für den unbedingten Sprung die
Bedingung auf wahr. Die vorhandene UND-Stufe `JNZ_TAKEN` und der
PC-Multiplexer in `FetchDecode` bleiben unverändert. Benannte Tunnel halten
die neue Verbindung von den dicht belegten Daten- und Fehlernetzen getrennt.

Die topologische Regression findet beide ODER-Gatter über ihre Labels, prüft
alle Quell- und Ziel-Tunnel sowie die beiden vorhandenen Eingänge von
`FetchDecode`. Ohne die neue Verbindung schlägt sie fehl. Die fokussierte
Abnahme lautet:

```bash
python3 -m unittest \
  tests.test_tiny_cpu_logisim.LogisimLauncherTests.test_unconditional_jump_reaches_common_pc_select
python3 src/tiny_cpu_verify.py
timeout 30s java -jar .venv/Include/logisim-evolution-4.1.0-all.jar \
  -tty stats hardware/logisim/TinyCPU.circ
scripts/test-offline.sh
```

- Die bisherigen Reparaturen schließen 19.8 noch nicht ab. `JUMP_ZERO`,
  `JUMP_NEGATIVE`, `JUMP_ERROR` und `JUMP_NOT_ERROR` besitzen weiterhin keinen
  Pfad zur gemeinsamen PC-Auswahl; gemäß Stop-Regel ist `JUMP_ZERO` der nächste
  zu untersuchende Übergang.
- Der isolierte `jump-address`-Matrixlauf erreicht weiterhin keinen
  beobachtbaren Normalhalt und läuft in den Timeout. Damit bleibt hinter der
  reparierten Steuerverbindung mindestens ein weiterer integrierter
  Unterschied offen; die Reparatur wird nicht als vollständige elektrische
  Sprungabnahme ausgegeben.
- Die vollständige elektrische Matrix und die GUI-Kurzabnahme bleiben Aufgabe
  19.9 vorbehalten.

### Fünfzehnte Reparatur: Nullsprung zum gemeinsamen PC-Auswahlpfad

Der nächste belegte Unterschied war `JUMP_ZERO`: Der Decoder führte das Signal
weiterhin nur zum Monitor, während der gemeinsame PC-Auswahlpfad nach der
vierzehnten Reparatur ausschließlich `JUMP_ADR` und `JUMP_NOT_ZERO` kannte.
Auch ein bei Akkumulatorwert null genommener Sprung konnte sein Ziel daher
nicht auswählen.

Eine zusätzliche ODER-Stufe nimmt `JUMP_ZERO` in die gemeinsame
Sprungsteuerung auf. Für die gemeinsame Bedingung wird der Nullsprung zuvor als
`JUMP_ZERO AND ZERO` qualifiziert und anschließend mit der bereits vorhandenen
Bedingung verknüpft. Diese Qualifizierung ist notwendig, damit ein nicht
genommener `JUMP_NOT_ZERO` bei gesetztem Nullflag nicht versehentlich durch den
neuen Zweig genommen wird. Das Nullflag wird direkt am bestehenden
`Datapath.ZERO`-Netz abgezweigt; Decoder und PC-Multiplexer bleiben
unverändert.

Die topologische Regression findet die drei neuen Gatter über ihre Labels und
prüft Decodersteuerung, Nullflag, Ergebnisnetze und beide vorhandenen
`FetchDecode`-Eingänge. Ohne die neuen Verbindungen schlägt sie fehl. Die
fokussierte Abnahme lautet:

```bash
python3 -m unittest \
  tests.test_tiny_cpu_logisim.LogisimLauncherTests.test_jump_zero_reaches_common_pc_select
python3 src/tiny_cpu_verify.py
timeout 30s java -jar .venv/Include/logisim-evolution-4.1.0-all.jar \
  -tty stats hardware/logisim/TinyCPU.circ
scripts/test-offline.sh
```

- Die bisherigen Reparaturen schließen 19.8 noch nicht ab. `JUMP_NEGATIVE`,
  `JUMP_ERROR` und `JUMP_NOT_ERROR` besitzen weiterhin keinen Pfad zur
  gemeinsamen PC-Auswahl; gemäß Stop-Regel ist `JUMP_NEGATIVE` der nächste zu
  untersuchende Übergang.
- Die vollständige elektrische Matrix und die GUI-Kurzabnahme bleiben Aufgabe
  19.9 vorbehalten.

### Sechzehnte Reparatur: Negativsprung zum gemeinsamen PC-Auswahlpfad

Der nächste belegte Unterschied war `JUMP_NEGATIVE`: Sein Decoder-Ausgang
endete weiterhin am Monitor und war nicht Teil der gemeinsamen PC-Auswahl.
Ein Sprung mit gesetztem Vorzeichenflag konnte deshalb das adressierte Ziel
nicht übernehmen.

Eine weitere ODER-Stufe ergänzt `JUMP_NEGATIVE` hinter der bereits
qualifizierten Nullsprungstufe. Der Bedingungszweig verknüpft
`JUMP_NEGATIVE AND NEGATIVE` und führt dieses Ergebnis mit der bisherigen
Taken-Bedingung zusammen. Das Vorzeichenflag wird am vorhandenen
`Datapath.NEGATIVE`-Netz abgezweigt. Der endgültige Ausgang behält die beiden
bestehenden Netznamen `ANY_JUMP_CONTROL` und `ANY_JUMP_CONDITION`, sodass die
Eingänge des PC-Multiplexers unverändert bleiben.

Die topologische Regression findet die drei neuen Gatter über ihre Labels und
prüft Decodersteuerung, Vorzeichenflag, beide Zwischenresultate und die
vorhandenen `FetchDecode`-Eingänge. Ohne die neuen Verbindungen schlägt sie
fehl. Die fokussierte Abnahme lautet:

```bash
python3 -m unittest \
  tests.test_tiny_cpu_logisim.LogisimLauncherTests.test_jump_negative_reaches_common_pc_select
python3 src/tiny_cpu_verify.py
timeout 30s java -jar .venv/Include/logisim-evolution-4.1.0-all.jar \
  -tty stats hardware/logisim/TinyCPU.circ
scripts/test-offline.sh
```

- Die bisherigen Reparaturen schließen 19.8 noch nicht ab. `JUMP_ERROR` und
  `JUMP_NOT_ERROR` besitzen weiterhin keinen Pfad zur gemeinsamen PC-Auswahl;
  gemäß Stop-Regel ist `JUMP_ERROR` der nächste zu untersuchende Übergang.
- Die vollständige elektrische Matrix und die GUI-Kurzabnahme bleiben Aufgabe
  19.9 vorbehalten.

### Siebzehnte Reparatur: Fehlersprung zum gemeinsamen PC-Auswahlpfad

Der nächste belegte Unterschied war `JUMP_ERROR`: Der Decoder-Ausgang endete
weiterhin am Monitor, und keines der sechs gespeicherten Fehlerbits erreichte
die gemeinsame Sprungbedingung. Ein Fehlersprung konnte daher auch bei
gesetztem Sticky-Flag sein adressiertes Ziel nicht übernehmen.

Ein sechsstufiger Fehler-Sammelpunkt bildet nun `ANY_ERROR_FOR_JUMP` direkt aus
`OVF`, `DIV0`, `ADDR`, `INV`, `ILL` und `INPUT`. Der Bedingungszweig
verknüpft dieses Ergebnis mit `JUMP_ERROR`; je eine weitere ODER-Stufe ergänzt
Decodersteuerung und qualifizierte Taken-Bedingung hinter den bereits
reparierten Negativsprungstufen. Die sechs öffentlichen Fehlerausgänge bleiben
auf ihren bisherigen, voneinander getrennten Netzen. Die beiden vorhandenen
Eingänge des PC-Multiplexers behalten ihre Funktion und werden nur um den neuen
Zweig erweitert.

Die topologische Regression findet alle vier neuen Gatter über ihre Labels,
prüft jeden der sechs Fehlerpfade sowie Decodersteuerung, Bedingung und die
beiden vorhandenen `FetchDecode`-Eingänge. Ohne eine der neuen Verbindungen
schlägt sie fehl. Die fokussierte Abnahme lautet:

```bash
python3 -m unittest \
  tests.test_tiny_cpu_logisim.LogisimLauncherTests.test_jump_error_reaches_common_pc_select
python3 src/tiny_cpu_verify.py
timeout 30s java -jar .venv/Include/logisim-evolution-4.1.0-all.jar \
  -tty stats hardware/logisim/TinyCPU.circ
scripts/test-offline.sh
```

- Die bisherigen Reparaturen schließen 19.8 noch nicht ab. `JUMP_NOT_ERROR`
  besitzt weiterhin keinen Pfad zur gemeinsamen PC-Auswahl und ist gemäß
  Stop-Regel der nächste zu untersuchende Übergang.
- Die vollständige elektrische Matrix und die GUI-Kurzabnahme bleiben Aufgabe
  19.9 vorbehalten.

### Nachprüfung nach der manuellen Symbolverschiebung

Die vollständige Offline-Suite zeigte nach der siebzehnten Reparatur fünf
strukturelle Regressionen aus der zwischenzeitlichen manuellen Anpassung der
Übersichtsseite. Die Bauteile der drei bereits reparierten Sprungstufen waren
verschoben worden, ihre Leitungsenden waren aber an den früheren
Eingangskoordinaten verblieben. Die Leitungen enden nun wieder an den
tatsächlichen Eingängen von `JUMP_ADR_OR_JNZ_CONTROL`,
`JUMP_ZERO_AND_ZERO`, `JUMP_NEGATIVE_AND_NEGATIVE` und den nachfolgenden
ODER-Stufen. Die Tests folgen den aktuellen Anschlüssen und schreiben die
überholte Symbolposition nicht wieder fest.

Außerdem hatten die vorhandene Konstante `0xfff` ihre Bezeichnung
`PROGRAM_LIMIT_MAX` und `MEMORY_WRITE_REQUEST` seine deklarierte Anzahl von
drei Eingängen verloren. Beide Attribute sowie die dritte, beim Redraw
abgetrennte Schreibanforderung sind wiederhergestellt. Damit bestehen die fünf
zuvor gemeldeten Regressionen und die vollständige Offline-Suite gemeinsam;
an Opcode-, Maschinenformat- oder VM-Vertrag wurde nichts geändert.

### Achtzehnte Reparatur: Sprung ohne Fehler zum gemeinsamen PC-Auswahlpfad

Der letzte in 19.7 nachgewiesene offene Sprungübergang war
`JUMP_NOT_ERROR`. Der Decoder-Ausgang erreichte zuvor ausschließlich seinen
Monitor. Nun invertiert `INVERT_ANY_ERROR_FOR_JUMP_NOT_ERROR` denselben aus
allen sechs Sticky-Flags gebildeten Sammelfehler, den auch `JUMP_ERROR`
verwendet. `JUMP_NOT_ERROR_AND_NO_ERROR` qualifiziert damit die
Taken-Bedingung. Zwei weitere ODER-Stufen ergänzen den Decodersteuerzweig und
die qualifizierte Bedingung hinter den zuvor reparierten Sprungstufen, ohne
deren Verbindungen zu ersetzen.

Die topologische Regression identifiziert alle vier neuen Gatter über Labels
und verfolgt Decodersteuerung, Sammelfehlerinvertierung, Taken-Bedingung und
beide gemeinsamen `FetchDecode`-Eingänge. Projektparser, Strukturprüfung und
Logisim-evolution 4.1.0 akzeptieren das geänderte Projekt. Damit sind alle fünf
in 19.7 als offen belegten Sprungsteuersignale an den PC-Auswahlpfad
angeschlossen und Aufgabe 19.8 ist abgeschlossen. Die vollständige elektrische
Profilmatrix und die GUI-Kurzabnahme bleiben Aufgabe 19.9 vorbehalten.

## 19.9 Vollständige elektrische Regression und GUI-Kurztest

### Ausgangslage

Die von Hand verschobenen Sprunggatter des Commits `1fdb161` wurden als neue
Ausgangsbasis kontrolliert; weder eine historische Schaltungsdatei noch deren
frühere Symbolkoordinaten wurden eingespielt. Dabei waren mehrere gezeichnete
Leitungen an den alten statt an den sichtbaren Gatteranschlüssen stehen
geblieben. Zusätzlich fehlte der Name `PROGRAM_LIMIT_MAX` erneut.

Die Leitungen wurden an den aktuellen Positionen rechtwinklig neu angelegt.
Die sechs Fehlerleitungen enden einzeln am verschobenen Sammelgatter, und die
Steuer- sowie Taken-Ketten erreichen wieder alle aktuellen Eingänge. Die
topologischen Regressionen wurden auf diese eingecheckte Anordnung
ausgerichtet; sie schreiben keine Vorgängerversion fest. Nur das mehrfach
verwendete `NEGATIVE`-Signal nutzt drei gleichnamige Tunnelanschlüsse: Eine
direkte senkrechte Fortsetzung hätte den verschobenen Akkumulatorbus sichtbar
gekreuzt und elektrisch verbunden. Die beiden abschließenden Sprungnetze
laufen stattdessen im freien unteren Außenkorridor direkt zurück zu
`FetchDecode`.

### Kommando oder Bedienfolge

```bash
python3 -m unittest tests.test_tiny_cpu_logisim -v
python3 src/tiny_cpu_verify.py
timeout 30s java -jar .venv/Include/logisim-evolution-4.1.0-all.jar \
  -tty stats hardware/logisim/TinyCPU.circ
LOGISIM_JAR=.venv/Include/logisim-evolution-4.1.0-all.jar \
  LOGISIM_OUTPUT=/tmp/tinycpu-ap19-9 LOGISIM_JOBS=4 \
  scripts/test-logisim.sh
```

### Beobachteter Nachweis

Die 34 fokussierten Logisim-Launcher- und Verdrahtungstests bestehen. Der
Verifier akzeptiert alle 14 JSON-Dateien, 30 Logisim-Projekte mit 81
Schaltungen und 4.460 rechtwinkligen Leitungen sowie den Vertrag aus 50
Opcodes und sechs Sticky-Fehlerfällen. Logisim-evolution 4.1.0 lädt
`TinyCPU.circ` im Statistikmodus ohne Diagnosefehler.

Die nachfolgende manuelle Neuanordnung ließ die `JumpBox` an ihrer neuen
Position. Bei der ersten Korrektur wurde die linke Symbolkante jedoch aus der
Instanzposition falsch abgeleitet: `(4360,450)` ist der Anker des ersten
Ausgangs, und die von Logisim erzeugte Box ist 220 Einheiten breit. Ihre 14
Eingänge liegen deshalb bei x=4140, nicht bei x=4060. Die vermeintliche
Korrektur auf x=4060 erzeugte genau die sichtbare 80-Einheiten-Lücke. Die
Leitungen enden nun wieder an der tatsächlichen Pinreihe bei x=4140; die
korrigierte Zuordnung der beiden Ausgänge bleibt erhalten. Die beim Redraw
erneut verlorene stabile Beschriftung `PROGRAM_LIMIT_MAX` wurde ebenfalls
wiederhergestellt, Wert und Anschluss der Konstante blieben unverändert.

Danach besteht der 16/12-Kerntrace wieder und alle 61 elektrischen
16/12-Fixtures einschließlich beider Pfade sämtlicher bedingter Sprünge sowie
der sechs Fehlerfälle stimmen mit dem Referenzmodell überein. Das gemeinsame Profilgate bestätigt den 16/12-Teil, erreicht beim unveränderten
8/8-Profil unter OpenJDK 25.0.2 jedoch innerhalb von 90 Sekunden keinen Halt;
dessen Matrix wird deshalb nicht gestartet. Die an die neue Anordnung
angepassten fokussierten Regressionen prüfen die sichtbaren Anschlusspunkte der
verschobenen Instanzen und nicht die Positionen vor dem Redraw.

### Offene Risiken

Der 16/12-Anteil von Aufgabe 19.9 ist automatisiert abgeschlossen. Der
unveränderte 8/8-Kerntrace muss noch mit der gepinnten Java-21-Umgebung
wiederholt werden. Der GUI-Kurztest ist in der nicht-interaktiven Umgebung
nicht sinnvoll ausführbar und bleibt ebenfalls offen. Aufgabe 19.10 darf
deshalb noch nicht als vollständig abgenommener Kandidat markiert werden; ein manueller Lauf muss
Reset, Takten, Ausgabe, Normalhalt und Fehlerhalt noch anhand der in
`hardware/logisim/README.md` dokumentierten Beobachtungspunkte bestätigen.

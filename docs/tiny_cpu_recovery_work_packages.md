# AP 20: Arbeitspakete zur Wiederherstellung der TinyCPU-Schaltungen

## Anlass

Der aktuelle Stand darf nicht als funktionsfähig vorausgesetzt werden. Der
schnelle Offline-Lauf bricht bereits bei `TinyCPU-8-8.circ` ab, weil dort noch
eine 16/12-Breite erkannt wird. Der gemeinsame elektrische Profiltest erreicht
weder für `TinyCPU.circ` noch für `TinyCPU-8-8.circ` den erwarteten Halt und
startet deshalb die einzelnen Opcode-Fälle nicht. Die detaillierte
Befehlsübersicht hält diesen Ausgangszustand fest.

AP 20 macht aus diesen zwei Befunden eine ausführbare Wiederherstellungsfolge.
Es ersetzt weder die Schaltungen durch historische Dateien noch ändert es ISA,
Opcode-Belegung oder Profilverträge. `TinyCPU.circ` bleibt die primäre
16/12-Schaltung; weil ihre verpflichtende Abnahme beide Profile umfasst, gehört
die Reparatur von `TinyCPU-8-8.circ` ausdrücklich zum Paket.

## Gemeinsame Regeln

Für jedes Arbeitspaket werden Ausgangs-Commit, exakter Befehl, Ergebnis und
erzeugte Artefakte im Diagnosebericht festgehalten. Eine Schaltungsänderung ist
erst zulässig, nachdem ein Test den ersten abweichenden benannten Port oder ein
falsches Bauteilattribut belegt. Nach jeder Reparatur laufen zuerst der neue
fokussierte Regressionstest, dann die Offline-Suite und zuletzt die kleinste
betroffene elektrische Abnahme.

Folgende Stop-Regeln gelten:

1. Keine ältere `.circ`-Datei als vermeintlich funktionierende Basis einspielen.
2. Keine Verdrahtung allein aufgrund früherer Canvas-Koordinaten verändern.
3. Nicht mehrere unabhängige Signalwege in einem Reparaturschritt ändern.
4. Einen Timeout zunächst als fehlenden Halt-Nachweis behandeln, nicht als
   Beweis für einen bestimmten Decoder-, Takt- oder Datenpfadfehler.
5. AP 18 (Peripherie und Interrupts) bleibt pausiert, bis beide CPU-Profile
   wieder ihre bestehenden Gates bestehen.

## Arbeitspakete

| Paket | Inhalt | Ergebnis | Abnahme |
|---|---|---|---|
| **20.1 Reproduktionsstand einfrieren** | Commit, Java- und Logisim-Version, JAR-Digest und Arbeitsbaumstatus erfassen. Offline- und elektrischen Profillauf unverändert ausführen; Ausgaben getrennt je Profil sichern. | Eine zweite Person kann beide aktuellen Fehler reproduzieren und erkennt, welcher Prüfschritt zuerst scheitert. | Der Diagnosebericht enthält Befehle, Exitcodes, Laufzeiten und Artefaktpfade; die Ausgangsdateien sind unverändert. |
| **20.2 Breitenfehler im 8/8-Profil isolieren** | Den vom Verifier gemeldeten 16/12-Rest auf Schaltung, Bauteil, Attribut und Profilregel zurückführen. Einen Regressionstest ergänzen und nur dieses Attribut beziehungsweise Netz korrigieren. | `TinyCPU-8-8.circ` erfüllt wieder ausschließlich den versionierten 8/8-Vertrag. | `python3 src/tiny_cpu_verify.py`, `python3 scripts/check-logisim-circuit.py` und der fokussierte Test bestehen; der Diff enthält keine fachfremde Neuverdrahtung. |
| **20.3 Offline-Baseline vollständig grün stellen** | Nach der Breitenkorrektur sämtliche statischen Topologie-, Profil-, Maschinenformat- und Unit-Tests ausführen. Weitere Befunde einzeln nach derselben Test-vor-Reparatur-Regel bearbeiten. | Strukturelle Fehler blockieren die elektrische Diagnose nicht mehr. | `scripts/test-offline.sh` besteht zweimal hintereinander in einem sauberen Arbeitsbaum. |
| **20.4 Reset, Takt und Fetch für 16/12 wiederherstellen** | Ein minimales ROM aus `LOAD_CONST` und `HALT` autonom ausführen. Reset, Clock, PC, ROM-Wort, Programmlimit und Halt von der ersten Flanke an mit dem VM-Trace vergleichen. | `TinyCPU.circ` erreicht deterministisch den normalen Halt; der erste frühere Unterschied ist durch einen benannten Regressionstest gesichert. | Zwei unabhängige Minimalprogrammläufe liefern denselben Endzustand und stimmen flankenweise mit der VM überein. |
| **20.5 Reset, Takt und Fetch für 8/8 wiederherstellen** | Den Nachweis aus 20.4 mit dem 8/8-Profil wiederholen, ohne Konstanten oder Erwartungen aus 16/12 zu übernehmen. Breitenabhängige Splitter, ROM/RAM und Grenzwerte gezielt prüfen. | Auch `TinyCPU-8-8.circ` erreicht den normalen Halt mit profilgerechten Signalbreiten. | Zwei unabhängige 8/8-Minimalprogrammläufe stimmen mit der VM überein; beide Profil-Kerntraces bestehen. |
| **20.6 ISA- und Fehlerregression schrittweise öffnen** | Zuerst je Profil eine Operation pro Familie prüfen, danach alle 50 Opcodes, beide Pfade jedes bedingten Sprungs und alle sechs Sticky-Fehlerfälle. Beim ersten Unterschied stoppen und nur dessen Signalkette reparieren. | Datenpfad, Adressierung, Sprünge, E/A, Halt und Fehlerzustände sind elektrisch für beide Profile nachgewiesen. | Die vollständigen Matrizen beider Profile bestehen gegen dasselbe Python-Referenzmodell; kein Fall wird übersprungen oder nur statisch bewertet. |
| **20.7 Redraw-sichere Regressionen ergänzen** | Für jeden gefundenen Defekt einen semantischen Struktur- oder elektrischen Test beibehalten. Tests folgen Labels, Ports und Netzkonnektivität statt absoluten Positionen; Multi-Driver, offene Eingänge und Breitenreste werden offline erkannt. | Ein erneutes Verschieben von Symbolen kann einen früheren Fehler nicht unbemerkt wieder einführen. | Die neuen Tests schlagen an einer gezielt defekten temporären Kopie fehl und am reparierten Projekt fehlersicher durch; die bestehende Suite bleibt grün. |
| **20.8 Endabnahme und Funktionsstatus aktualisieren** | In frischem Checkout Offline-Gate und komplettes Logisim-Gate ausführen, anschließend den dokumentierten GUI-Kurztest für Reset, Einzeltakt, Ausgabe, Normalhalt und Fehlerhalt durchführen. Befehlsstatus und Diagnosebericht aus den Ergebnissen aktualisieren. | Der veröffentlichte Status beschreibt wieder Nachweise statt Absichten; ein konkreter Commit ist als funktionsfähiger Kandidat reproduzierbar. | Beide automatischen Gates bestehen zweimal, der GUI-Kurztest ist protokolliert, und alle 50 Befehle werden nur bei vorhandenem elektrischen Nachweis als funktionsfähig markiert. |

## Reihenfolge und Parallelität

20.1 bis 20.3 laufen strikt nacheinander. Danach dürfen 20.4 und 20.5 getrennt
analysiert werden, sofern Reparaturen weiterhin einzeln integriert und gegen
beide Profile geprüft werden. 20.6 beginnt erst mit zwei grünen Kerntraces.
20.7 wird während jeder Reparatur mitgeführt, seine Abnahme erfolgt aber erst
nach der vollständigen Matrix. 20.8 ist das einzige Paket, das den
Funktionsstatus auf „funktionsfähig“ setzen darf.

## Definition of Done

Die Wiederherstellung ist abgeschlossen, wenn ein frischer Checkout mit der
unterstützten Logisim-evolution-Version alle folgenden Nachweise liefert:

```bash
scripts/test-offline.sh
LOGISIM_JAR=path/to/logisim-evolution-4.1.0-all.jar scripts/test-logisim.sh
```

Zusätzlich muss der GUI-Kurztest aus `hardware/logisim/README.md` dokumentiert
sein. Ein erfolgreiches Laden der Projekte, ein grüner Verifier oder ein
einzelner funktionierender Opcode genügt jeweils nicht. Große Rohtraces gehören
in das Artefaktverzeichnis und nicht in Git; eingecheckt werden Schaltungen,
fokussierte Regressionstests sowie die zusammengefassten Nachweise.

## Nicht Bestandteil

- neue Befehle oder Änderungen an der ISA;
- neue Daten- oder Adressbreiten;
- Peripherie- und Interruptintegration aus AP 18;
- ein optischer Redraw ohne belegten elektrischen Fehler;
- das Absenken von Prüfanforderungen, Timeouts oder Matrixabdeckung, um einen
  fehlerhaften Lauf grün erscheinen zu lassen.

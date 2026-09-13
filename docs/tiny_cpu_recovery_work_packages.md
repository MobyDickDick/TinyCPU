# AP 20: Arbeitspakete zur Wiederherstellung der TinyCPU-Schaltungen

## Anlass

Das experimentelle 8/8-Profil wurde stillgelegt. Die sechs Opcode-Bits der
16/12-TinyCPU stellen bereits die benötigte Anzahl an Befehlen bereit; eine
zweite, schlecht wartbare Schaltung ist dafür nicht erforderlich. Historische
8/8-Diagnosen in Bericht und Git-Historie bleiben nachvollziehbar, sind aber
keine aktuellen Abnahmeziele.

AP 20 konzentriert sich damit ausschließlich auf `TinyCPU.circ`. Das nächste
aktive Paket ist 20.4: Reset, Takt und Fetch des 16/12-Profils. ISA und
Opcode-Belegung bleiben unverändert.

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
5. AP 18 (Peripherie und Interrupts) bleibt pausiert, bis die 16/12-CPU
   wieder ihr bestehendes Gate besteht.
6. `FetchDecodeControls` wird nicht erneut umgezeichnet, automatisch
   angeordnet oder optisch „aufgeräumt“. Falls seine Darstellung vergrößert
   werden muss, darf ausschließlich das gesamte vorhandene Bild in beiden
   Achsen mit demselben Faktor skaliert werden; relative Bauteilpositionen und
   Leitungsverläufe bleiben unverändert. Die verbindlichen Bearbeitungsregeln
   stehen zusätzlich in `hardware/logisim/AGENTS.md`.

## Arbeitspakete

| Paket | Inhalt | Ergebnis | Abnahme |
|---|---|---|---|
| **20.1 Reproduktionsstand einfrieren** | Commit, Java- und Logisim-Version, JAR-Digest und Arbeitsbaumstatus erfassen. Offline- und elektrischen Profillauf unverändert ausführen; Ausgaben getrennt je Profil sichern. | Eine zweite Person kann beide aktuellen Fehler reproduzieren und erkennt, welcher Prüfschritt zuerst scheitert. | Der Diagnosebericht enthält Befehle, Exitcodes, Laufzeiten und Artefaktpfade; die Ausgangsdateien sind unverändert. |
| **20.2 Historischer Breitenbefund (erledigt, Profil stillgelegt)** | Die frühere Reparatur bleibt in der Historie dokumentiert; das zugehörige Profil wurde entfernt. | Kein aktuelles Ergebnis: 8/8 ist kein unterstütztes Profil mehr. | Die Stilllegung wird durch fehlende Artefakte und die Ablehnung des Profilnamens geprüft. |
| **20.3 Offline-Baseline vollständig grün stellen** | Nach der Breitenkorrektur sämtliche statischen Topologie-, Profil-, Maschinenformat- und Unit-Tests ausführen. Weitere Befunde einzeln nach derselben Test-vor-Reparatur-Regel bearbeiten. | Strukturelle Fehler blockieren die elektrische Diagnose nicht mehr. | `scripts/test-offline.sh` besteht zweimal hintereinander in einem sauberen Arbeitsbaum. |
| **20.4 Reset, Takt und Fetch für 16/12 wiederherstellen** | Ein minimales ROM aus `LOAD_CONST` und `HALT` autonom ausführen. Reset, Clock, PC, ROM-Wort, Programmlimit und Halt von der ersten Flanke an mit dem VM-Trace vergleichen. | `TinyCPU.circ` erreicht deterministisch den normalen Halt; der erste frühere Unterschied ist durch einen benannten Regressionstest gesichert. | Zwei unabhängige Minimalprogrammläufe liefern denselben Endzustand und stimmen flankenweise mit der VM überein. |
| **20.6 ISA- und Fehlerregression schrittweise öffnen** | Zuerst eine Operation pro Familie prüfen, danach alle 50 Opcodes, beide Pfade jedes bedingten Sprungs und alle sechs Sticky-Fehlerfälle. Beim ersten Unterschied stoppen und nur dessen Signalkette reparieren. | Datenpfad, Adressierung, Sprünge, E/A, Halt und Fehlerzustände sind elektrisch für das 16/12-Profil nachgewiesen. | Die vollständige Matrix des 16/12-Profils besteht gegen dasselbe Python-Referenzmodell; kein Fall wird übersprungen oder nur statisch bewertet. |
| **20.7 Redraw-sichere Regressionen ergänzen** | Für jeden gefundenen Defekt einen semantischen Struktur- oder elektrischen Test beibehalten. Tests folgen Labels, Ports und Netzkonnektivität statt absoluten Positionen; Multi-Driver, offene Eingänge und Breitenreste werden offline erkannt. | Ein erneutes Verschieben von Symbolen kann einen früheren Fehler nicht unbemerkt wieder einführen. | Die neuen Tests schlagen an einer gezielt defekten temporären Kopie fehl und am reparierten Projekt fehlersicher durch; die bestehende Suite bleibt grün. |
| **20.8 Endabnahme und Funktionsstatus aktualisieren** | In frischem Checkout Offline-Gate und komplettes Logisim-Gate ausführen, anschließend den dokumentierten GUI-Kurztest für Reset, Einzeltakt, Ausgabe, Normalhalt und Fehlerhalt durchführen. Befehlsstatus und Diagnosebericht aus den Ergebnissen aktualisieren. | Der veröffentlichte Status beschreibt wieder Nachweise statt Absichten; ein konkreter Commit ist als funktionsfähiger Kandidat reproduzierbar. | Die automatischen Gates bestehen zweimal, der GUI-Kurztest ist protokolliert, und alle 50 Befehle werden nur bei vorhandenem elektrischen Nachweis als funktionsfähig markiert. |

## Reihenfolge und Parallelität

20.1 bis 20.3 sind historisch abgeschlossen. 20.4 läuft als nächstes aktives Paket; 20.5 entfällt mit der Stilllegung des 8/8-Profils. 20.6 beginnt erst mit einem grünen 16/12-Kerntrace.
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

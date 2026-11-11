# AP 22.3: ausführbare aktuelle Dokumentation

Stand: 11. November 2026. **Status: abgeschlossen.** Dieses Paket korrigiert Einstiegs- und Referenzseiten
und prüft deren Beispiele; es ist keine elektrische Release-Neuabnahme.

## Umfang

Der Dokumentationsindex trennt aktuelle Bedien-/Referenzseiten, verbindliche
Schaltplanregeln und historische Projektaufzeichnungen. Die aktuelle
Prüfliste steht in `tests/test_tiny_cpu_documentation.py` und umfasst 15 Seiten.
Die früheren Logisim-Aufbauschritte sind in `hardware/logisim/HISTORY.md`
mit unverändertem historischem Inhalt erhalten. Historische Release Notes
sind ausdrücklich als solche gekennzeichnet; ihre
alten Befehle bleiben Projektgeschichte. Planungsstände werden nicht als
aktuelle Bedienanleitung ausgegeben.

Quickstart und Architektur verwenden den vorhandenen Debugger statt einer
fehlenden CLI oder des nicht ausführenden VM-Moduls. Sechs Beispiele prüfen
Countdown, Speicheraddition, gültige Eingabe, fehlende Eingabe, Fehlerhalt und
Breakpoint. Die Tests lesen die Befehle und die vollständige Sollausgabe direkt
aus beiden Seiten und prüfen stdout, leeres stderr und Exitcode. Eine feste
Liste verhindert, dass versehentlich entfernte Beispiele unbemerkt bleiben.
Die drei kurzen Zusatzprogramme stehen unter `docs/examples/`.

Eine dabei geklärte Semantik: `HALT()` bleibt auch mit Sticky-Flags ein normaler
Halt mit CLI-Exitcode 0. Fehlende Eingabe und anschließendes PRINT setzen INPUT
und INV, erzeugen aber keine Ausgabe. Explizites `HALT_ERROR()` liefert Exit 1.
Dieser Befund korrigiert die Dokumentation, ohne VM oder Schaltung zu ändern.

Die aktuellen Seiten nennen nur das unterstützte 16/12-Basisprofil, das bereits
implementierte Operator-Panel und die verpflichtende vollständige elektrische
Matrix. Die Abdeckung der lokalen Nachweise vom 10. November bleibt von einem
allgemeinen Äquivalenzbeweis, einem neuen Linux-Lauf, AP 22.5 und der weiterhin
offenen interaktiven GUI-Abnahme getrennt.

## Reproduktion und Nachweis

Basiscommit: `37d996a5d81874e05e4d01c53ceeec664fd68061` plus die durch
`candidate-files.json` mit SHA-256 identifizierten Änderungen dieses Pakets.
Es wurde kein neuer Commit erstellt.

Die Prüfung verwendet einen frisch aus `git archive HEAD` extrahierten
Quellstand mit genau diesen Änderungen. Er enthält weder den lokalen Cache
noch die vorhandene `.venv`, Artefakte oder unversionierte Hilfsdateien.
`PYTHONPATH` wird entfernt. Das ist ein frischer Quellsnapshot des Kandidaten,
kein neuer Linux-CI-Lauf und keine AP-22.5-Releasequalifikation.

Nachweisverzeichnis: `artifacts/documentation-ap22-3-20261111/`.
`acceptance.py` erzeugt Snapshot, Dateiinventar und `results.json`, führt alle
Befehle im Snapshot aus und bewahrt stdout/stderr samt Exitcodes auf.

Ausgeführte Befehle (Windows, Python 3.14.5):

```powershell
python src/tiny_cpu_verify.py
python scripts/check-logisim-circuit.py
python -m unittest discover -s tests -v
python -m unittest discover -s tests -p test_tiny_cpu_documentation.py -v
```

Der letzte Befehl führt die sechs veröffentlichten Programmläufe ohne
PYTHONPATH und die lokalen Datei-/Überschriftenlinks der aktuellen Seiten aus.
Die vollständige Suite enthält diese Prüfungen ebenfalls; der gezielte Lauf
bewahrt einen kurzen separaten Nachweis der Dokumentationsabnahme auf.

Ergebnis: Alle vier Aufrufe liefern **Exitcode 0**. Verifikator und
Strukturprüfung bestehen, die vollständige Windows-Suite enthält **296 Tests**
ohne Fehler oder übersprungene Tests. Beide Dokumentationstests bestehen;
ihre sechs Teilaufrufe liefern exakt die dokumentierte Ausgabe und die
Exitcodes 0 beziehungsweise beim expliziten Fehlerhalt 1.
`verify.txt`, `structure.txt`, `unit.txt` und `documentation.txt` bewahren die
vollständigen Ausgaben auf.

AP 22.3 ist damit abgeschlossen. Es wurden keine Schaltungen oder VM-Pfade
geändert und keine neue elektrische Abnahme behauptet. Als nächster
Pflichtschritt bleibt der Linux-Nachweis aus AP 22.4; danach folgt AP 22.5.

# Symbolischer TinyCPU-Debugger

Der Debugger führt Programme auf dem pausierbaren Python-Referenzmodell aus.
Er verändert weder Maschinenformat noch Logisim-Schaltung. `.tcpu`-Quellen
werden durch denselben Assemblerpfad geladen; reine `v2.0 raw`-ROM-Dateien
funktionieren mit Adress-Breakpoints, besitzen aber keine Quellmetadaten.

## Aufruf

Vom Repository-Wurzelverzeichnis aus:

```bash
python3 src/tiny_cpu_debugger.py hardware/logisim/ap5_countdown.tcpu \
  --breakpoint loop
python3 src/tiny_cpu_debugger.py hardware/logisim/ap5_countdown.tcpu --step
python3 src/tiny_cpu_debugger.py hardware/logisim/ap5_countdown.tcpu --json
python3 src/tiny_cpu_debugger.py program.tcpu --profile tinycpu-8-8 --json
```

Ein erster Lauf mit dem Breakpoint `loop` liefert beispielsweise:

```text
stop=breakpoint pc=4 steps=4
ACC=3 valid=true AR=0 valid=false ZERO=false NEGATIVE=false
errors=- output=[]
memory_changes=[{'address': 100, 'value': 3, 'valid': True}, {'address': 101, 'value': -1, 'valid': True}]
```

Die Kommandozeile ist absichtlich ein **Einmal-Aufruf**: Sie lädt das Programm,
führt entweder genau einen Schritt (`--step`) oder `continue` aus, gibt einen
Stoppzustand aus und beendet sich. Für eine Sitzung mit mehreren abwechselnden
`step`-/`continue`-Aufrufen dient die unten beschriebene Python-Schnittstelle.

`--breakpoint`/`-b` darf wiederholt werden und akzeptiert ein Label oder eine
Instruktionsadresse. Breakpoints stoppen **vor** der bezeichneten Instruktion.
Ohne `--step` läuft das Programm bis zu Breakpoint, Halt, Fehlerhalt oder
`--step-limit`. `--input` füllt wiederholbar die Eingabewarteschlange.
Unbekannte Labels und Adressen außerhalb des Programms werden vor der
Ausführung abgelehnt.

Weitere wichtige Optionen:

- `--input WERT` legt einen ganzzahligen Wert in die Eingabewarteschlange; die
  Option kann für mehrere `INPUT`-Instruktionen wiederholt werden;
- `--step-limit N` begrenzt die insgesamt ausgeführten Instruktionen (Standard:
  `10000`), damit beispielsweise eine Endlosschleife deterministisch endet;
- `--json` ersetzt die Textausgabe durch das unten beschriebene JSON-Objekt.
- `--profile tinycpu-16-12|tinycpu-8-8` wählt Daten-/Adressbreite und
  Maschinenformat; ohne diese Option bleibt `tinycpu-16-12` der Standard.

Ein normaler Halt und ein Breakpoint liefern Exit-Code `0`. `halt_error` und
`step_limit` liefern Exit-Code `1`; fehlerhafte Argumente, nicht assemblierbare
Quellen und ungültige Breakpoints werden von `argparse` mit Exit-Code `2`
gemeldet. Damit kann der Debugger auch in Skripten eingesetzt werden.

## Mehrere Stopps mit der Python-Schnittstelle

Das folgende Beispiel stoppt bei jedem Besuch von `loop`, führt die dortige
Instruktion aus und setzt das Programm anschließend fort:

```python
from pathlib import Path
import sys

sys.path.insert(0, str(Path("src").resolve()))

from tiny_cpu_assembler import load_program
from tiny_cpu_debugger import Debugger

debugger = Debugger(load_program(Path("hardware/logisim/ap5_countdown.tcpu")))
debugger.add_breakpoint("loop")

state = debugger.continue_()
while state["stop_reason"] == "breakpoint":
    print(state["pc"], state["accumulator"])
    debugger.step()                 # Breakpoint-Instruktion genau einmal ausführen
    state = debugger.continue_()    # bis zum nächsten Besuch oder zum Halt

print(state["stop_reason"], state["output"])
```

`remove_breakpoint` löscht einen Breakpoint wieder. `read_memory(100)` liest
eine einzelne Zelle; `read_memory(100, 110)` liest den geschlossenen Bereich
100 bis 110. Beide Formen liefern für jede Zelle `address`, `value` und
`valid`. Bereichsgrenzen außerhalb des gewählten Profils (`0..4095` oder
`0..255`) werden abgelehnt.

Die Python-Schnittstelle `Debugger` bietet zusätzlich `add_breakpoint`,
`remove_breakpoint`, `step`, `continue_` und `read_memory(start, end)`. Ein
erneutes `step` oder `continue_` nach Programmende gibt den unveränderten
Endzustand zurück.

## JSON-Vertrag

`--json` schreibt genau ein kanonisch sortiertes JSON-Objekt. Der Vertrag
`tinycpu-debug-v1` liegt maschinenlesbar in
`hardware/logisim/tinycpu-debug-v1.json`. `schema_version` ist derzeit `1`;
Konsumenten müssen unbekannte Felder ignorieren. `stop_reason` ist einer von:

- `breakpoint`: PC steht vor einer Breakpoint-Instruktion;
- `step`: genau eine Instruktion wurde ausgeführt;
- `halt` oder `halt_error`: endgültiger Haltzustand;
- `step_limit`: das feste Ausführungslimit wurde erreicht.

Jeder Stopp nennt `profile` und `machine_format` und enthält PC und optionale
Quellzeile, Akkumulator und Adressregister
jeweils als Wert/Validitäts-Paar, Zero/Negative, alle sechs Sticky-Fehlerbits,
Ausgaben sowie seit dem vorherigen Stopp veränderte Speicherzellen. Ungelesene
oder ungültige Speicherwerte werden niemals als gültige Null dargestellt.

`memory_changes` gilt jeweils seit dem vorherigen erzeugten Stoppzustand. Beim
Abruf eines Zustands wird diese Änderungsliste geleert; für eine unveränderte,
gezielte Speicherinspektion sollte deshalb `read_memory` verwendet werden.
`source` ist bei einem reinen ROM-Image `null`, weil darin keine Quellzeilen
oder Labels gespeichert sind.

## Fehlerdiagnose

- **`unknown label 'name'`:** Das Label kommt in der geladenen `.tcpu`-Quelle
  nicht vor. Bei `.rom`-Dateien stattdessen eine numerische Adresse verwenden.
- **`breakpoint address … is outside the loaded program`:** Die Adresse zeigt
  nicht auf eine geladene Instruktion.
- **`stop=step_limit`:** Das Ausführungslimit wurde erreicht. Den Programmfluss
  auf eine Endlosschleife prüfen oder bewusst ein größeres `--step-limit`
  angeben.
- **`stop=halt_error`:** Die CPU hat wegen eines Laufzeitfehlers angehalten.
  Das gesetzte Sticky-Flag steht in `errors`; ungültige Operanden sind außerdem
  an den jeweiligen `valid`-Feldern erkennbar.

## Abnahme

Die Offline-Suite prüft Label- und Adressfehler, wiederholte Countdown-
Breakpoints, Einzelschritt-Parität, alle sichtbaren Fehler-/Validitätszustände
und bytegleiche JSON-Ausgaben:

```bash
scripts/test-offline.sh
```

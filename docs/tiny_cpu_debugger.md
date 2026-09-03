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
```

`--breakpoint`/`-b` darf wiederholt werden und akzeptiert ein Label oder eine
Instruktionsadresse. Breakpoints stoppen **vor** der bezeichneten Instruktion.
Ohne `--step` läuft das Programm bis zu Breakpoint, Halt, Fehlerhalt oder
`--step-limit`. `--input` füllt wiederholbar die Eingabewarteschlange.
Unbekannte Labels und Adressen außerhalb des Programms werden vor der
Ausführung abgelehnt.

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

Jeder Stopp enthält PC und optionale Quellzeile, Akkumulator und Adressregister
jeweils als Wert/Validitäts-Paar, Zero/Negative, alle sechs Sticky-Fehlerbits,
Ausgaben sowie seit dem vorherigen Stopp veränderte Speicherzellen. Ungelesene
oder ungültige Speicherwerte werden niemals als gültige Null dargestellt.

## Abnahme

Die Offline-Suite prüft Label- und Adressfehler, wiederholte Countdown-
Breakpoints, Einzelschritt-Parität, alle sichtbaren Fehler-/Validitätszustände
und bytegleiche JSON-Ausgaben:

```bash
scripts/test-offline.sh
```

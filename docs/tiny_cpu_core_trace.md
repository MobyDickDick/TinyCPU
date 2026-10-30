# Elektrischer Kernvergleich (AP 22.1)

**Stand: 30. Oktober 2026.** Der Vergleich ist im verpflichtenden Gate aktiv.
Die Schaltung besteht die Abnahme derzeit nicht. Nach der begrenzten
`STORE_ADDRESS`-Reparatur bestehen beide Minimalkernläufe und die neue
STORE-Regression einschließlich Negativkontrolle. Der Countdown scheitert
erstmals an Flanke 5, `pre`, bei `PRINT_ENABLE` (Soll `1`, Ist `0`). Die
Bestandsaufnahme mit 59 Abweichungen in 61 ISA-/Fehler-Fixtures stammt vom
29. Oktober; die Matrix wurde nach dem neuen ersten Fehler nicht wiederholt.
Reproduktion und nächste Diagnose stehen im
[Diagnosebericht](tiny_cpu_circuit_debug_report.md#ap-221-store_address-ladeanforderung-am-30-oktober-2026).

## Ausführung

Voraussetzungen sind Python, Java ab Version 21 und Logisim-evolution 4.1.0.
Das vollständige Gate bleibt:

```bash
scripts/test-logisim.sh
```

Der Kernvergleich allein:

```bash
PYTHONPATH=src python src/tiny_cpu_logisim.py \
  --trace-output artifacts/core/core.tsv --matrix-output artifacts/core/isa
```

`--java` und `--jar` wählen explizite lokale Laufzeiten. Unter PowerShell
wird `PYTHONPATH` vorher mit `$env:PYTHONPATH='src'` gesetzt. Der normale
serielle Lauf stoppt bei der ersten fehlerhaften Fixture. `run_matrix()`
vergleicht jede der unveränderten 61 Fixtures; ein grüner Halt ersetzt
keinen Zustandsvergleich. `run_core_acceptance()` prüft den Minimalkern
zweimal auf Parität und Determinismus sowie die ursprüngliche Countdown-Fixture.

## Beobachtungsvertrag

`scripts/LogisimCoreTrace.java` öffnet mit den öffentlichen APIs der gepinnten
JAR eine ROM-Kopie und steuert den Eingang `CLK` selbst. Der Export erhält
keine VM-Sollwerte. Er löst bestehende Instanzen und Pins über ihre Labels auf;
es werden keine Beobachtungspins, Ersatzschaltungen oder Canvas-Koordinaten
in die geprüfte Schaltung eingefügt.

Der TSV-Header lautet `edge`, `phase`, danach die in
`src/tiny_cpu_core_trace.py:SIGNALS` festgelegten Spalten und `MEMORY`.
Signalwerte sind Binärzahlen mit genau der angegebenen Breite, ohne Präfix.
Flanken werden ab 1 gezählt. Pro Instruktion gibt es genau zwei Beobachtungen:

1. `pre`: `CLK=0`, nach vollständiger Propagierung. Register, Ausgabeereignisse,
   Schreibanforderung und die vor der Flanke anliegenden Daten werden geprüft.
2. `post`: nach `CLK=1` und vollständiger Propagierung. PC, Akkumulator,
   Adressregister, Gültigkeitsbits, alle sechs Sticky-Flags und der gesamte
   RAM-Inhalt werden mit genau einem VM-Schritt verglichen.

`HALTED` und `HALTED_WITH_ERROR` sind kombinatorische Terminalereignisse des
aktuellen Befehls. Der Export erkennt sie in `pre`, führt noch die zugehörige
Flanke aus und endet nach `post`. Damit werden auch die Fehlerflags eines
illegalen Befehls geprüft. Nach der Flanke gehört die neue Decoderbelegung
bereits zum nächsten PC; sie wird erst beim nächsten `pre` als Ereignis
bewertet. Ein gespeichertes Hardware-Haltregister wird nicht vorausgesetzt.

Die beiden PRINT-Kanäle werden getrennt nach Enable, Wert und Gültigkeit
geprüft, einschließlich ungültiger Ausgabeversuche. Speicherprüfungen umfassen
die tatsächliche Schreibfreigabe, Adresse, Wert und Gültigkeit sowie den
asynchronen Lesebus bei Speicherbefehlen. `MEMORY` enthält die vollständige,
nach Adresse sortierte Liste aller RAM-Zellen mit Wert ungleich null oder
gesetzter Gültigkeit: `Adresse:Wert:Gültigkeit`, durch Kommas getrennt, oder
`-` für ausschließlich `0 INVALID`. Unerwartete Änderungen und veraltete
ungültige Daten sind dadurch ebenfalls sichtbar. Spätere Lesezugriffe werden
zusätzlich über den elektrischen Lesebus und das Zielregister geprüft.

Die Eingänge sind ausdrücklich gesetzt: `RESET` pulst bei `CLK=0` und fällt
vor der ersten Flanke; danach ist es null. Interrupt- und externe
Speichereingänge sind null, `USE_EXTERNAL_MEMORY=0` wählt internen RAM.
`RAM_WRITE_ENABLE=0` ist in diesem Modus unselektiert. Neue unbekannte
Eingangspins lassen den Export scheitern.

**Offene Eingabegrenze:** `TinyCPUMain` besitzt derzeit keine öffentlichen
`INPUT_VALUE`-/`INPUT_VALID`-Pins. Die Eingabefälle verwenden deshalb ausdrücklich
Wert `0`, Gültigkeit `0` beziehungsweise eine leere VM-Eingabequeue. Diese
Festlegung steht je Lauf in `inputs.json`. Sie ist kein Nachweis einer
funktionierenden gültigen Eingabe. Deren elektrische Schnittstelle und Abnahme
bleiben innerhalb AP 22.1 offen; die bestehende ISA wird dafür nicht erweitert.

Der Comparator lehnt fehlende, zusätzliche oder vertauschte Beobachtungen,
fehlende/zusätzliche Spalten, falsche Bitbreiten und jeden undefinierten oder
elektrischen Fehlerwert ab, auch auf momentan inaktiven beobachteten Bussen.
Ein Logisim-Prozessfehler oder Timeout kann nicht bestehen. Zeilenanzahlen
einer änderungsgetriebenen `-tty table`-Ausgabe werden nie als Flankenzahl
interpretiert; der alte Tabellenlauncher bleibt ausschließlich Diagnosehilfe.

## Nachweise und Negativkontrolle

Neben jeder Rohdatei `name.tsv` bleibt ein Ordner `name/` mit injiziertem
Projekt, `probes.tsv`, `inputs.json`, `expected.json`, exaktem `command.json`
und unverändertem `stderr.txt` erhalten. Der erste Vergleichsfehler erzeugt
`diagnostic.json` mit Fixture, Flanke, Phase, Signal, Soll und Ist. Bei Timeout
bleibt auch eine unvollständige Rohdatei erhalten. CI lädt diese Artefakte
weiterhin über den bestehenden Upload-Schritt hoch.

```bash
PYTHONPATH=src python scripts/test-logisim-core-mutation.py
```

Diese zusätzlich verpflichtende Kontrolle prüft zuerst unverändert
`LOAD_CONST(3); HALT`. Nur in einer gesonderten Kopie fügt sie anschließend
einen 16-Bit-Inverter vor das Laden des Akkumulators ein. Der tatsächliche
Akkumulatorwert ist dann `65532` (`-4`) statt `3`; Normalhalt bleibt erreicht.
Das Gate muss an Flanke 1, `post`, Signal `ACC` ablehnen. Das ist eine
Mutation des Ergebnisdatenpfads, kein Additions-/Divisionsgrenzfallnachweis.
Originalschaltungen bleiben bytegleich. `proof.json` dokumentiert sowohl
die erfolgreiche unveränderte Kontrolle als auch die abgelehnte Mutation.

Die ergänzende verpflichtende STORE-Regression läuft separat:

```bash
PYTHONPATH=src python scripts/test-logisim-store.py
```

Sie prüft `LOAD_CONST(-1); STORE_ADDRESS(101); HALT` und den gleichen Ablauf
mit gültiger `0` vollständig gegen die VM, einschließlich Akkumulatorhalten,
Speicherwert und -gültigkeit sowie Halt. Anschließend setzt sie ausschließlich
in einer Kopie die benannte neutrale Konstante `ACC_STORE_DISABLED` auf `1`.
Der Vergleich muss dann an Flanke 2, `post`, `ACC` (Soll `65535`, Ist `0`)
ablehnen. Das ist eine Negativkontrolle der fehlerhaften Ladeanforderung;
sie verdrahtet keine historische Zeichnung zurück. Ungültiges Speichern und
andere Decoderterme sind damit nicht vollständig abgenommen.

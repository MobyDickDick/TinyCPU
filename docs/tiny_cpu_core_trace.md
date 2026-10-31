# Elektrischer Kernvergleich (AP 22.1)

**Stand: 31. Oktober 2026.** Der Vergleich ist im verpflichtenden Gate aktiv.
Beide identischen Minimalkernläufe, der vollständige Countdown und alle
61 bestehenden ISA-/Fehlerfixtures bestehen jetzt mit vollständigem
Pre-/Post-Zustandsvergleich. Der CI-Fehler bei `load-address-register` ist
behoben; auch die danach einzeln geöffneten Pfade sind korrigiert und erneut
abgenommen. Die Bestandsaufnahme mit 59 Abweichungen vom 29. Oktober ist
historisch. Gültige externe Eingaben, weitere arithmetische Grenzen aus 22.2
und die Neuabnahme aus frischem Checkout nach 22.5 bleiben offen. Reproduktion
und Abdeckungsgrenzen stehen im
[Diagnosebericht](tiny_cpu_circuit_debug_report.md#ap-221-registerpfade-und-vollständige-61-fall-abnahme-am-31-oktober-2026).

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
Der Vergleich muss dann an Flanke 2, `post`, `ACC` (Soll `65535`, abweichender
definierter Istwert) ablehnen und den tatsächlichen falschen Wert in
`proof.json` festhalten. Nach der korrigierten Speicherladeauswahl ist dieser
Wert `101`; der frühere inaktive Buswert `0` ist kein Maschinenvertrag.
Das ist eine Negativkontrolle der fehlerhaften Ladeanforderung;
sie verdrahtet keine historische Zeichnung zurück. Ungültiges Speichern und
andere Decoderterme sind damit nicht vollständig abgenommen.

Die ebenfalls verpflichtende PRINT-Regression läuft separat:

```bash
PYTHONPATH=src python scripts/test-logisim-print.py
```

Sie vergleicht `LOAD_CONST(3); PRINT(); HALT`, den gleichen Ablauf mit `-1`,
gültige Null mit zwei aufeinanderfolgenden PRINT-Befehlen und einen Lauf ohne
PRINT vollständig mit der VM. Damit werden Enable, Wert, Gültigkeit,
Akkumulatorhalten und Normalhalt gemeinsam geprüft. Anschließend trennt sie
ausschließlich in einer Kopie den über benannte Pins aufgelösten PRINT-Zweig
und legt ihn auf Null. Der Vergleich muss an Flanke 2, `pre`, `PRINT_ENABLE`
(Soll `1`, Ist `0`) ablehnen, während Normalhalt erhalten bleibt. Original-
schaltung, Rohdaten und `proof.json` werden entsprechend geprüft beziehungsweise
aufbewahrt. Zwei zusätzliche Positivkontrollen prüfen inzwischen auch einen
ungültigen PRINT-Versuch mit INV-Übernahme und `PRINT_ADDRESS` aus gültigem RAM.

Die verpflichtende Immediate-Regression läuft separat:

```bash
PYTHONPATH=src python scripts/test-logisim-immediate.py
```

Sie vergleicht `LOAD_CONST(3); ADD_CONST(-1); HALT` sowie eine Addition mit
gültigem Nullergebnis vollständig mit der VM. Eine Kopie unterdrückt nur den
Konstantenselektor und muss an Flanke 2, `post`, `ACC` (Soll `2`, Ist `0`)
abgelehnt werden. Die Rohdaten müssen zusätzlich `ACC_VALID=0` und
`ERROR_INV=1` belegen: Die reparierte Ergebnisgültigkeit macht den Fehler nun
bereits am kanonischen ungültigen Nullergebnis sichtbar.
Eine zweite Kopie ersetzt nur `Operations.IMMEDIATE_VALUE` durch Null und muss
an derselben Flanke bei `ACC` (Soll `2`, Ist `3`) scheitern. Originalschaltung,
Rohtraces und `proof.json` werden entsprechend geprüft beziehungsweise erhalten.
Der ebenfalls verpflichtende `scripts/test-logisim-decode.py` prüft nun auch
`ACC_MEMORY_REQUEST` für sämtliche 64 Opcodezeilen, insbesondere seine drei
Speicherlade-Terme. Die übrigen offenen Register- und Fehlerfälle sind durch
diese gezielten Prüfungen nicht freigegeben.

Der Decodertest prüft außerdem `ACC_WRITE_REQUEST=0` für
`LOAD_ADDRESS_REGISTER_CONST` (`0x27`). Eine gesonderte Kopie entfernt nur die
neutrale Konstante `ACC_LD_REG_CONST_DISABLED` und stellt den belegten
`LD_REG_CONST`-Zweig zur Akkumulator-Ladeanforderung wieder her. Die gesamte
64-Zeilen-Prüfung muss dann ausschließlich an Opcode `0x27` bei
`ACC_WRITE_REQUEST` (Soll `0`, Ist `1`) ablehnen. Unveränderte Quelle,
Projektkopien, Befehle und beide Rohtraces werden unter `artifacts/decode/`
beziehungsweise dem mit `--output` gewählten Pfad festgehalten. Dieser Nachweis
betrifft das Akkumulatorhalten. Die zusätzliche verpflichtende Prüfung
`scripts/test-logisim-address-register.py` vergleicht neun Programme für
Konstanten, Halten, erneutes Laden, Registerlesen/-schreiben, positive und
negative Offsets sowie das Laden aus RAM vollständig mit der VM. Fünf Kopien
erzwingen einen aktiven Reset, unterdrücken Laden beziehungsweise
Registerauswahl, verfälschen den Datenwert oder aktivieren den falschen Carry
bei negativem Offset. Jede muss am festgelegten ersten Unterschied scheitern.
Rohtraces, Projektkopien und `proof.json` bleiben unter dem `--output`-Pfad.

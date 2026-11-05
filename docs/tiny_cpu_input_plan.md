# AP 22.1: Externe Eingabe – Schnittstelle und Abnahme

**Stand: 4. November 2026. Status:** Das begrenzte Planungspaket ist
abgeschlossen; die elektrische Implementierung und Eingabeabnahme sind offen.
Ausgangsstand ist Commit `1e7a8f6`. Dieses Dokument legt den nächsten
Funktionsschritt aus der [Qualitätsplanung](tiny_cpu_quality_work_packages.md)
fest. Die produktiven `.circ`-Dateien wurden in diesem Paket nicht geändert.

## Ausgangspunkt und Ziel

Die VM unterstützt eine Eingabewarteschlange. Der aktuelle öffentliche Kern
`TinyCPUMain` besitzt dagegen weder Eingabewert noch Eingabegültigkeit.
`expected_trace()` verwendet deshalb ausdrücklich eine leere Warteschlange;
`LogisimCoreTrace.java` treibt nur die neun vorhandenen Kerneingänge.
Eine erfolgreiche Fixture mit `INPUT()` belegt bisher nur den Fehlerfall.

Im aktuellen `AccumulatorUnit` wählt Steuerbit 34 (`INPUT`) eine feste Null
als Ladegültigkeit. `FaultUnit` führt denselben Decode zum Eingabefehler.
Ein späterer Umbau muss Daten, Gültigkeit und Fehleranforderung gemeinsam
prüfen. Eine alleinige Einspeisung des Werts würde gültige Eingaben weiterhin
als ungültig behandeln. Vor Änderungen sind diese Wege passiv elektrisch zu
messen; die Bestandsaufnahme der XML-Netze ersetzt diesen Nachweis nicht.

Ziel ist eine Eingabe pro ausgeführtem `INPUT()` mit festgelegtem Wert und
Gültigkeit. Opcode, 22-Bit-Instruktionsformat, 16/12-Profil und bestehende
Fehlersemantik bleiben erhalten. Tastatur, Dateidialog, Warteschlangen-Hardware,
Wartezustände und asynchrone Handshakes sind nicht Bestandteil.

## Geplante öffentliche Grenze

Die Eingabe wird über einen zusätzlichen, ausdrücklich gewählten Teilkreis
`TinyCPUInputMain` im bestehenden Kernprojekt angeboten. Dies ist kein neues
Hardwareprofil und kein separates CPU-Projekt. Der bisherige `TinyCPUMain`
mit seinen neun Eingängen und 24 Ausgängen bleibt die kompatible Grenze für
Peripherieprojekt, Operator-Panel und bestehende Werkzeuge. Deren Schaltungen
werden nicht durch neue, unbeschaltete Eingänge beeinträchtigt.

`TinyCPUInputMain` übernimmt die acht fachlichen Aufgaben und alle bisherigen
Pins nach Name, Richtung und Breite. Nur Akkumulator- und Fehlerbox benötigen
Eingabevarianten (`AccumulatorInputUnit`, `FaultInputUnit`); die sechs anderen
Boxen und die vorhandenen Blattbausteine werden gemeinsam benutzt. Die
Varianten teilen sich weiterhin `Datapath` und `ErrorFlags` mit der Baseline.
Ein späteres Zusammenführen der öffentlichen Grenzen ist ein eigenes
Kompatibilitätspaket, kein stiller Austausch des bisherigen Symbols.

Zusätzlich gelten folgende Pins; die Namen sind für die Umsetzung reserviert,
im aktuellen Projekt aber noch nicht vorhanden:

| Pin | Richtung am Kern | Breite | Bedeutung |
| --- | --- | --- | --- |
| `INPUT_VALUE` | Eingang | 16 | Zweierkomplement-Bitmuster des angebotenen Werts |
| `INPUT_VALID` | Eingang | 1 | 1: erfolgreicher Leseversuch; 0: keine oder ungültige Eingabe |
| `INPUT_CONSUME` | Ausgang | 1 | Leseanforderung des aktuellen `INPUT`; Transaktion an der steigenden Flanke |

`INPUT_CONSUME` ist bei aktivem `INPUT` und inaktivem Reset 1, sonst 0.
Es ist kein eigener Takt und keine zusätzliche Flanke. Der Anbieter wertet
es zusammen mit der steigenden CPU-Flanke aus. Auch ein fehlgeschlagener
Leseversuch erzeugt diese Anforderung. Eine vorhandene ungültige Eingabe wird
dabei verbraucht; bei leerer Quelle bleibt die Quelle leer. Zwei direkt
aufeinanderfolgende INPUT-Befehle können den Pegel durchgehend auf 1 halten;
die zwei CPU-Flanken sind dennoch zwei Transaktionen.

Die Quelle legt Wert und Gültigkeit in der niedrigen Taktphase vor `pre` an
und hält sie bis nach der zugehörigen `post`-Messung. Erst danach darf sie
zum nächsten Eintrag wechseln. Außerhalb einer INPUT-Transaktion darf sie
wechseln, ohne Akkumulator, Speicher oder Fehlerflags zu verändern. Während
Reset darf keine Eingabe verbraucht werden. Alle Treiber verwenden auch bei
`INPUT_VALID=0` ein definiertes 16-Bit-Muster; `E` und `U` sind Prüffehler.

## Architektur und Fehlervertrag

Bei `INPUT_VALID=1` übernimmt die INPUT-Flanke `INPUT_VALUE` und setzt
`ACC_VALID=1`. Jedes 16-Bit-Muster ist ein gültiger vorzeichenbehafteter Wert;
insbesondere ist `0xffff` der Wert -1. Es gibt auf diesem Bus keinen
zusätzlichen darstellbaren Zahlenbereichsfehler.

Bei `INPUT_VALID=0` übernimmt die Flanke unabhängig vom Datenmuster
`0 INVALID` und setzt ausschließlich die Fehlerursache `INPUT`. Der PC geht
normal weiter; es gibt weder Warten noch automatischen Fehlerhalt. Ein späterer
gültiger INPUT stellt die Akkumulatorgültigkeit wieder her, löscht aber das
Sticky-Flag nicht. `CLEAR_ERROR` löscht Flags und hält Wert sowie Gültigkeit.
Ein ungültiger PRINT danach kann als eigene Ursache `INV` setzen.

Der Host-Adapter prüft ganzzahlige Eingaben vor der Busabbildung gegen
`-32768..32767`. Beispielsweise darf 32768 nicht einfach als gültiges
Bitmuster `0x8000` angeboten werden: Es wird mit `INPUT_VALID=0` abgebildet.
Die VM bleibt bei ihrer bestehenden `list[int]`-Schnittstelle. Für einen
flankenbezogenen Test speist der Referenzadapter vor dem betreffenden
VM-Schritt entweder den vorzeichenrichtig dekodierten Wert oder eine leere
Warteschlange ein. Eine ausdrücklich ungültige Host-Eingabe wird zusätzlich
mit ihrem ursprünglichen Wert getestet. Leere und ungültige Quelle haben
denselben CPU-Zustand, aber der Testanbieter protokolliert ihre unterschiedliche
Verbrauchsfolge. Erwartete Verbrauchsereignisse werden nicht aus der VM abgelesen.

## Verbindliche Abnahmefälle

Die festen Erwartungen unten ergänzen den vollständigen VM-Vergleich.
Insbesondere dürfen die Sollwerte der Grenzfälle nicht erst aus der VM
berechnet werden. `tests/test_tiny_cpu_vm.py:InputContractTests` prüft bereits
die Softwareseite einschließlich Warteschlangenverbrauch und Speicherweg;
das ist noch kein elektrischer Nachweis.

| Fall | Vorgabe und unabhängig festgelegte Erwartung |
| --- | --- |
| Gültige Werte | Je `INPUT; PRINT; HALT` mit 0, -1, -32768 und 32767: gleicher ACC-/Ausgabewert, gültig, kein Fehler. |
| Fehlende Eingabe | Nach gültigem ACC=7: INPUT ohne Angebot liefert `0 INVALID`, INPUT=1, INV=0 und fortgeschrittenen PC. |
| Ungültige Eingabe | `INPUT_VALID=0` mit Datenmustern 0, `0x8000`, `0xffff`: stets `0 INVALID` und nur INPUT als neue Fehlerursache. |
| Host-Grenzen | -32769 und 32768 werden ungültig angeboten und verbraucht; gültiges -32768 bleibt gültig. |
| Zwei direkt aufeinanderfolgende INPUT | Angebote 0 und -1: zwei Transaktionen, einmaliger Verbrauch je Flanke und richtige Reihenfolge. |
| Zwischenschritte | INPUT, PRINT, INPUT mit Angeboten 0 und -1: PRINT verbraucht keinen Eintrag; bei drittem INPUT ist die Quelle leer. |
| Erholung | Ungültiger INPUT, gültiger INPUT=23, CLEAR_ERROR: ACC wird gültig, INPUT bleibt bis CLEAR_ERROR gesetzt; danach ACC unverändert gültig. |
| Nur Fehler löschen | Fehlgeschlagener INPUT, CLEAR_ERROR: ACC bleibt `0 INVALID`, alle Flags gelöscht. |
| Speicherweg | INPUT=-32768, STORE(101), LOAD_CONST(7), LOAD(101), PRINT: RAM und Ausgabe enthalten -32768 mit Gültigkeit 1. |
| Keine INPUT-Ausführung | Wechselnde externe Werte/Gültigkeit bei LOAD_CONST, PRINT, HALT sowie übersprungenem INPUT: kein Verbrauch und keine fremden Zustandsänderungen. |
| Reset | Gültiges Angebot während Reset wird nicht verbraucht; erster ausgeführter INPUT nach Reset übernimmt es genau einmal. |

Ein neuer fokussierter Treiber `scripts/test-logisim-input.py` soll jeden Fall
seriell bis zum ersten Unterschied ausführen. Zusätzlich benötigt er mindestens
drei unabhängige Fehlerkopien: falscher Eingabewert bei weiterhin korrektem
Halt, erzwungene Ladegültigkeit bei ungültiger Eingabe und unterdrücktes
`INPUT_CONSUME`. Jede Kopie muss an ihrer festgelegten ersten Flanke und ihrem
benannten Signal abgelehnt werden.

Der Kerntrace wird um die drei Pins mit festen Breiten erweitert. `pre`
prüft Angebot und Verbrauch, `post` die unveränderten bisherigen Zustandsfelder
einschließlich RAM. Der Java-Exporter erhält ausschließlich Stimuli und keine
VM-Sollzustände. `inputs.json` bewahrt pro Flanke Wert, Gültigkeit und
gegebenenfalls Host-Originalwert auf. Fehlende oder zusätzliche Stimuluszeilen,
unbekannte Felder, falsche Breiten und E/U-Werte brechen die Abnahme ab.
Ein gesondertes Verbrauchsprotokoll des Testanbieters erkennt doppelte und
ausgelassene Transaktionen. Der volle Comparator bleibt für jede Fixture aktiv.

## Umsetzung in einzeln prüfbaren Schritten

1. **Als Nächstes: passive INPUT-Baseline.** `LOAD_CONST(7); INPUT; HALT`
   unverändert am bisherigen Kern ausführen. Um die INPUT-Flanke Decode,
   Datapath-Daten, Ladefreigabe und Ladegültigkeit sowie `ErrorFlags.SET_INPUT`
   und den übernommenen Fehlerzustand über benannte Pfade beobachten. Den
   bisherigen Fehlerfall gegen die leere VM-Quelle prüfen und die künftig zu
   erweiternden Netze benennen. Eine fehlende öffentliche Eingabe ist kein
   Beleg für eine defekte Leitung in diesem bisherigen Fehlerfall.
   Noch keine Leitungsänderung und keine vollständige Matrixwiederholung.
2. Die zusätzliche Grenze und die zwei Boxvarianten implementieren; dabei die
   bestehenden sechs Boxen und alle ursprünglichen Blattdefinitionen, besonders
   den geschützten Decoder, bytegleich erhalten. Für jeden Daten-, Gültigkeits-
   und Fehlerpfad zuerst den benannten elektrischen Nachweis sichern, dann nur
   die kleinste belegte Änderung vornehmen. Zeichenstil und native Sichtprüfung
   gelten auch für die Varianten.
3. Stimulusvertrag, Exporter und Comparator erweitern; den ersten gültigen
   INPUT und anschließend die Fälle oben sowie ihre Mutationen abnehmen.
4. Den neuen Treiber in `scripts/test-logisim.sh` verpflichtend einbinden.
   Bestehende Kernfixtures außerdem mit dem Eingabetop und explizit inaktiver
   Eingabe ausführen; Baseline, System- und Operator-Gates müssen weiter bestehen.
   Erst danach die offene Eingabe-Checkbox in AP 22.1 schließen.

Beim ersten elektrischen Unterschied wird gestoppt. Timeouts, neue E/U-Werte
und andere Fehlerketten dürfen weder durch abgesenkte Anforderungen noch
durch gleichzeitige Reparaturen mehrerer Wege übergangen werden. Ein
abgebrochener Versuch bleibt unter `artifacts/`; ein Rückbau entfernt nur die
zusätzliche Eingabegrenze und ihre Treiber. Bestehende ROMs und die Baseline
bleiben ohne Konvertierung ausführbar.

## Wiederhergestellte Prüfgrundlage dieses Pakets

Die bisherigen STORE-/Decoder-Negativkontrollen erwarteten entfernte
Nullkonstanten an `ACC_LOAD_REQUEST.14` beziehungsweise `.12`. Der Fehler
wurde reproduziert. Beide Adapter ergänzen jetzt ausschließlich in Wegwerfkopien
den benannten verbotenen Term am Ausgang: `ACC_WRITE_REQUEST OR STORE_ADR`
beziehungsweise `ACC_WRITE_REQUEST OR LD_REG_CONST`. Bestehende Gattereingänge
und Konstanten sind dafür unerheblich. Die Originalzeichnung wird nicht
gespeichert. Der STORE-Adapter prüft nun ebenfalls ausdrücklich deren Bytegleichheit.

Die Nachweise liegen unter `artifacts/ap22-input-contract-20261104/`:

| Prüfung | Ergebnis |
| --- | --- |
| Elektrischer Decoder | Alle 64 Kontrollzeilen bestanden, einschließlich `ACC_WRITE_REQUEST` in jeder Zeile. Auch alle 64 Mutationszeilen geprüft: ausschließlich Opcode 39 weicht bei `ACC_WRITE_REQUEST` ab, Soll 0, Ist 1. `decode-final/proof.json`. |
| Elektrischer STORE | -1 und gültige Null bestanden; Fehlerkopie an Flanke 2 post bei ACC abgelehnt: Soll 65535, Ist 101. `store-after/proof.json`. |
| Strukturprüfung | `python scripts/check-logisim-circuit.py`, Exit 0; `structure.txt`. |
| Windows-Unit-Suite | 248 Tests, vier bestehende Rasterfehlschläge, kein Adapterfehler mehr; `unit-after.txt`. Die Ausgangssuite hatte 241 Tests, dieselben vier Rasterfehlschläge und einen Adapterfehler. |
| Vollständiger Offline-Verifikator | Weiterhin Exit 1 am bestehenden FetchUnit-Rasterbefund; `verify.txt`. Die Regeln wurden nicht gelockert. |

Die elektrische Umgebung verwendet die vorhandene gepinnte Logisim-JAR 4.1.0,
OpenJDK 27 und Python 3.14.5. PowerShell-Aufrufe:

```powershell
$env:PYTHONPATH='src'
$env:JAVA='C:/Program Files/jdk-27/bin/java.exe'
$env:LOGISIM_JAR=(Resolve-Path .venv/Include/logisim-evolution-4.1.0-all.jar).Path
$env:TEMP=(Resolve-Path artifacts/ap22-input-contract-20261104/tmp).Path
$env:TMP=$env:TEMP
$env:JAVA_TOOL_OPTIONS='-Djava.util.prefs.PreferencesFactory=LocalPreferencesFactory -Xbootclasspath/a:C:/Users/marku/myCloud/TinyCPU/artifacts/address-validity-20261104/prefs'
python scripts/test-logisim-decode.py --output artifacts/ap22-input-contract-20261104/decode-final
python scripts/test-logisim-store.py --output artifacts/ap22-input-contract-20261104/store-after
python -m unittest discover -s tests -v
```

Die Preferences-Hilfsklassen sind lokale, nicht versionierte Testartefakte aus
der vorigen Abnahme. Die elektrischen `command.json`-Dateien und Rohdaten
bleiben bei den jeweiligen Fällen erhalten. Es gab keinen Simulator-Download.
Die offenen Rasterbefunde betreffen FetchUnit, AccumulatorUnit, MemoryUnit und
FaultUnit. Sie bleiben eine eigene Layoutaufgabe. Dieses Planungspaket ist
weder die vollständige AP-22.1-Abnahme noch eine Release- oder GUI-Abnahme.

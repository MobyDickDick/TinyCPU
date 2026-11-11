# TinyCPU in Logisim-evolution

Aktuelle Befehle und Abnahmegrenzen stehen im
[Testleitfaden](../../docs/tiny_cpu_test_guide.md) und im
[Funktionsstatus](../../docs/tiny_cpu_instruction_status.md). Unterstützt ist
nur das Basisprofil `tinycpu-16-12`; das optionale Peripheriesystem und das
Operator-Panel sind implementiert. Die lokale elektrische Abnahme vom
10. November ersetzt weder AP 22.5 noch den weiterhin offenen manuellen
GUI-Kurztest unten. Spätere datierte Protokolle auf dieser Seite bleiben
historische Nachweise ihrer jeweiligen Kandidaten.

Kurze Erklärungen der Grundfunktion stehen jeweils in einer `.md`-Datei neben
der gleichnamigen `.circ`-Datei. Der [CPU-Kern](TinyCPU.md) beschreibt alle
29 eingebetteten Teilkreise; ergänzend gibt es Beschreibungen für
[Peripherie und Interrupts](TinyCPU_Peripherals.md), das
[Operator-Panel](TinyCPU_Operator.md) sowie sämtliche Diagnose- und Smoke-Dateien.
Damit sind einschließlich der beiden neuen Adress-Gültigkeitsbausteine alle
58 Teilkreisdefinitionen im Bestand erfasst.

`TinyCPUMain` ist die Übersicht aus acht Funktionsboxen. Die Detailverdrahtung
liegt in den jeweiligen Teilkreisen; auf der obersten Ebene stehen nur diese
Boxen, öffentliche Anschlusspins und Leitungen. Architektur, Abbildung und
Abnahmen sind in [AP 23](../../docs/tiny_cpu_modularity_plan.md) dokumentiert.
Die Strukturregel in [AGENTS.md](AGENTS.md) und der Offline-Verifier schützen
diese Aufteilung bei späteren Änderungen.

## Manueller GUI-Kurztest

Dieser Kurztest ergänzt die automatischen Gates; er ersetzt weder
`scripts/test-offline.sh` noch `scripts/test-logisim.sh`. Er ist mit
Logisim-evolution 4.1.0 an einem Desktop mit sichtbarer Anzeige auszuführen:

### Logisim unter Linux starten

`DISPLAY` ist nur die Adresse eines bereits laufenden X-Servers; die Variable
allein erzeugt keine Anzeige. Auf einem Linux-Desktop ist sie normalerweise
schon gesetzt und kann vor dem Start aus dem Wurzelverzeichnis dieses
Repositories geprüft werden:

```bash
test -n "${DISPLAY:-}" && printf 'DISPLAY=%s\n' "$DISPLAY"
java -jar /pfad/zu/logisim-evolution-4.1.0-all.jar hardware/logisim/TinyCPU.circ
```

Bei einer SSH-Verbindung muss X11-Forwarding auf Server und Client erlaubt
sein. `ssh -X host` (gegebenenfalls `ssh -Y host`) setzt `DISPLAY` in der
entfernten Sitzung automatisch; ein manuelles `export DISPLAY=:0` ist nur
richtig, wenn unter `:0` tatsächlich ein erreichbarer X-Server läuft und die
Sitzung darauf zugreifen darf. Für einen Container müssen sowohl die
`DISPLAY`-Variable als auch der X11-Socket des Hosts durchgereicht werden, zum
Beispiel mit `-e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix:rw`; auch dabei muss
der Host den Zugriff ausdrücklich erlauben. `Xvfb` kann zwar einen virtuellen
X-Server bereitstellen, ersetzt aber ohne sichtbare und bediente Oberfläche
nicht den hier verlangten manuellen Sichtnachweis.

#### Ubuntu-/Debian-Container mit sichtbarem VNC-Desktop

Für einen Ubuntu- oder Debian-Container installiert das versionierte
Hilfsskript Java 21, Xvfb, Fluxbox, x11vnc und die benötigten
X11-Diagnosewerkzeuge:

```bash
cd /workspace/TinyCPU
./gui.sh install
./gui.sh check
./gui.sh start
```

Das Präfix `./` ist erforderlich, weil das aktuelle Verzeichnis unter Linux
absichtlich nicht automatisch zum Suchpfad für Programme gehört. Der Befehl
heißt daher **nicht** `gui.sh install` und ebenfalls nicht
`scripts-setup-logisim-gui.sh install`. Alternativ kann das lange Skript
explizit an Bash übergeben werden:

```bash
bash scripts/setup-logisim-gui.sh install
```

Der Installationsbefehl eignet sich auch als Setup-Skript einer
Container-Umgebung. Die beiden Folgebefehle werden anschließend im
interaktiven Terminal ausgeführt, weil beim Image-Aufbau gestartete Prozesse
nicht dauerhaft weiterlaufen. Der VNC-Server lauscht absichtlich ohne Passwort
ausschließlich auf `localhost:5900`. Von einem lokalen Rechner wird er deshalb
nur über einen SSH-Tunnel erreicht:

```bash
ssh -L 5900:localhost:5900 BENUTZER@HOST
```

Nach dem Verbinden eines lokalen VNC-Viewers mit `localhost:5900` wird Logisim
im Container gestartet:

```bash
./gui.sh run
```

Der sichtbare Desktop kann danach beendet werden:

```bash
./gui.sh stop
```

`TINYCPU_DISPLAY`, `TINYCPU_VNC_PORT` und `LOGISIM_JAR` überschreiben bei
Bedarf Displaynummer, lokalen VNC-Port und JAR-Pfad. Ein bloß gestartetes, aber
nicht über VNC betrachtetes und manuell bedientes Xvfb erfüllt die GUI-Abnahme
weiterhin nicht. Stellt die Container-Plattform weder einen sichtbaren Desktop
noch einen erreichbaren beziehungsweise tunnelbaren TCP-Port bereit, muss der
Kurztest auf einem lokalen Desktop ausgeführt werden.

### Logisim unter Windows/Git Bash starten

Unter Windows wird `DISPLAY` für eine native Java-Anwendung nicht benötigt.
Insbesondere ist `DISPLAY=needs-to-be-defined` keine verwendbare Anzeige; die
Linux-Prüfung oben ist in Git Bash daher nicht aussagekräftig. Entscheidend ist
zuerst, dass ein JDK ab Version 21 installiert und `java.exe` über `PATH`
auffindbar ist:

```bash
java.exe --version
command -v java.exe
```

Meldet Git Bash `java.exe: command not found`, muss zuerst ein JDK installiert
oder dessen `bin`-Verzeichnis in den Windows-`PATH` aufgenommen werden. Danach
Git Bash neu öffnen und die beiden Prüfungen wiederholen.

Ist das JDK beispielsweise unter `C:\Program Files\jdk-27\bin` installiert,
kann Git Bash die native Windows-EXE direkt über den entsprechenden
Git-Bash-Pfad aufrufen. Die Anführungszeichen sind wegen des Leerzeichens in
`Program Files` erforderlich:

```bash
"/c/Program Files/jdk-27/bin/java.exe" --version
"/c/Program Files/jdk-27/bin/java.exe" -jar \
  './.venv/Include/logisim-evolution-4.1.0-all.jar' \
  hardware/logisim/TinyCPU.circ
```

Alternativ kann das Verzeichnis für die aktuelle Git-Bash-Sitzung in `PATH`
aufgenommen werden. `hash -r` verwirft dabei die gemerkte erfolglose
Befehlssuche:

```bash
export PATH="/c/Program Files/jdk-27/bin:$PATH"
hash -r
java.exe --version
```

Für eine dauerhafte Lösung sollte `C:\Program Files\jdk-27\bin` in den
Windows-Benutzer-`PATH` eingetragen und Git Bash danach neu gestartet werden.
Git Bash kann Windows-Programme mit der Endung `.exe` direkt ausführen; es ist
keine getrennte Linux-VM, deren Betriebssystemgrenze Java überwinden müsste.
Für das elektrische Gate lässt sich der absolute Java-Pfad ohne dauerhafte
`PATH`-Änderung außerdem ausdrücklich übergeben:

```bash
JAVA='/c/Program Files/jdk-27/bin/java.exe' scripts/test-logisim.sh
```

Aus dem Wurzelverzeichnis dieses Repositories kann die vorhandene JAR bei
eingerichtetem `PATH` anschließend so gestartet werden:

```bash
JAR='./.venv/Include/logisim-evolution-4.1.0-all.jar'
test -f "$JAR" || { printf 'JAR fehlt: %s\n' "$JAR" >&2; exit 1; }
java.exe -jar "$JAR" hardware/logisim/TinyCPU.circ
```

Der Pfad `/pfad/zu/...` aus dem Linux-Beispiel ist nur ein Platzhalter und darf
nicht wörtlich übernommen werden. Liegt die JAR an einer anderen Stelle, muss
`JAR` entsprechend auf den tatsächlich vorhandenen Pfad zeigen. Ein
`export DISPLAY=:0` behebt weder ein fehlendes Java noch eine fehlende JAR.

1. `TinyCPU.circ` öffnen, `TinyCPUMain` wählen und mit **Simulation > Reset
   Simulation** zurücksetzen. Anschließend mit dem Poke-Werkzeug den externen
   Eingang `CLK` auf `0`, `RESET` kurz auf `1` und wieder auf `0` setzen.
   `PC_VALUE` muss danach `0` zeigen, beide Haltausgänge und alle sechs
   Fehlerausgänge müssen `0` sein.
2. **Simulation > Ticks Enabled** ausgeschaltet lassen. `TinyCPUMain` besitzt
   einen externen `CLK`-Eingang und keinen internen Clock-Baustein; deshalb
   erzeugt **Simulation > Manual Tick Full Cycle** hier keine CPU-Flanke.
   Stattdessen mit dem Poke-Werkzeug `CLK` für jeden vollen Einzeltakt einmal
   von `0` auf `1` und wieder auf `0` schalten. Der PC muss sich pro steigender
   Flanke entsprechend dem Countdown-Programm ändern; beim ersten `PRINT`
   müssen `PRINT_ENABLE=1`, `PRINT_VALID=1` und `PRINT_VALUE=3` sein. Die
   folgenden Ausgaben sind `2` und `1`.
3. Bis zum normalen Ende weiter takten. Dann muss `HALTED=1` und
   `HALTED_WITH_ERROR=0` sein. Nach einem erneuten Reset müssen PC und beide
   Haltausgänge wieder den Zustand aus Schritt 1 zeigen.
4. Für die getrennte Fehlerhaltprobe in einer Arbeitskopie die ersten beiden
   ROM-Einträge durch `0x230001` (`LOAD_CONST 1`) und `0x370000`
   (`HALT_ERROR`) ersetzen, erneut resetten und einen vollen Einzeltakt
   auslösen. Während am PC danach der zweite Befehl decodiert wird, muss
   `HALTED=0` und `HALTED_WITH_ERROR=1` sein. Die Arbeitskopie danach
   verwerfen; die eingecheckte Schaltung darf durch den Kurztest nicht geändert
   werden.

Das Protokoll nennt Datum, getesteten Commit, Logisim-/Java-Version und die
beobachteten Werte aller vier Schritte. Ein bloßes erfolgreiches Öffnen der
Datei ist keine GUI-Abnahme.

### `U` oder `E` statt `0`/`1` im GUI-Kurztest

Logisim zeigt einen gesetzten booleschen Ausgang als `1`. Die Anzeige `E` am
Pin `HALTED_WITH_ERROR` bedeutet daher **nicht**, dass die CPU regulär mit
Fehler angehalten hat, sondern dass Logisim auf diesem Netz einen elektrischen
Fehlerwert berechnet. `U` bedeutet einen noch unbekannten beziehungsweise
undefinierten Wert. Eine Aufnahme mit `U` an `HALTED` und `E` an
`HALTED_WITH_ERROR` ist deshalb kein erwarteter Fehlerhaltzustand.

In diesem Fall keine weiteren Takte auslösen und die geöffnete Datei nicht
speichern. Zuerst Logisim schließen, im Repository einen unveränderten Stand
prüfen und die Eingangsbelegung der eingecheckten Datei tabellarisch laden:

```bash
git status --short
JAR='./.venv/Include/logisim-evolution-4.1.0-all.jar'
java -jar "$JAR" -tty table hardware/logisim/TinyCPU.circ
```

In der Tabelle müssen für alle vier Kombinationen von `CLK` und `RESET` die
beiden letzten Spalten `HALTED` und `HALTED_WITH_ERROR` zunächst `0` sein. Ist
das der Fall, die GUI mit genau derselben JAR erneut öffnen, **Simulation >
Reset Simulation** ausführen und anschließend den oben beschriebenen
RESET-Impuls sowie die manuell am Eingangs-Pin erzeugten `CLK`-Flanken
verwenden. Liefert bereits der Tabellenbefehl `E`, muss vor dem GUI-Kurztest
eine unveränderte Arbeitskopie des dokumentierten Kandidaten verwendet werden;
der fehlerhafte Stand darf nicht als AP-20.8-Nachweis protokolliert werden.

### Leitungsfarben sind kein Verdrahtungsnachweis

Die Farben einer laufenden Simulation dürfen nicht mit offenen oder falsch
verbundenen Leitungen verwechselt werden. Insbesondere zeigen die breiten
Daten- und Adressbusse je nach aktuellem Mehrbitwert schwarz oder orange; die
einbittigen Steuersignale erscheinen dagegen grün. Ein orangefarbener Bus ist
daher für sich allein **kein** elektrischer Fehler. Maßgeblich sind `E` an
einem Ausgang, ein rotes Konfliktnetz oder eine fehlgeschlagene elektrische
Abnahme.

### Wiederherstellung nach einer fehlerhaften Verdrahtungsänderung

Die Integrationsseiten müssen **nicht von Hand neu verdrahtet** werden. Wenn
eine Änderung entfernte Leitungen wieder eingefügt oder die drei erzeugten
Bausteinsymbole gegen alte Koordinaten verdrahtet hat, Logisim ohne Speichern
schließen und die beiden betroffenen Projektdateien aus dem letzten
nachweislich guten Commit wiederherstellen:

```bash
git status --short
git restore --source=<GUTER_COMMIT> -- \
  hardware/logisim/TinyCPU.circ \
  hardware/logisim/TinyCPU_Peripherals.circ
scripts/test-offline.sh
scripts/test-logisim.sh
```

`<GUTER_COMMIT>` ist dabei der geprüfte Stand vor der fehlerhaften Änderung,
nicht irgendeine ältere Schaltungskopie. Anschließend zeigt `git diff` exakt,
welche Änderung zurückgenommen wird. Ein bloßes Nachzeichnen anhand eines
Screenshots oder veralteter Koordinaten ist nicht zulässig: Die erzeugten
Symbolkontakte hängen von der aktuellen Pin-Reihenfolge ab und eine optisch
anliegende Leitung kann deshalb am falschen Port enden. Erst wenn die
Wiederherstellung beide Gates besteht, darf die Datei wieder in der GUI
geöffnet werden.

Die eingecheckte Verdrahtung wird ohne Bedienzustand der GUI vollständig mit
dem echten Logisim-Simulator geprüft:

```bash
scripts/test-logisim.sh
```

Der Lauf führt das Countdown-Programm zweimal aus und prüft anschließend alle
50 Opcodes sowie sechs Sticky-Fehlerfälle. Erst ein Fehler dieses Laufs ist ein
reproduzierbarer Funktionsbefund. Bleibt nur die sichtbare Integrationsseite
nach dem Öffnen stehen, ist das erwartbar: `TinyCPUMain` besitzt einen externen
`CLK`-Pin. Nach **Simulation > Reset Simulation** müssen deshalb zuerst der
oben beschriebene RESET-Impuls und anschließend manuelle `CLK`-Flanken erzeugt
werden; **Manual Tick Full Cycle** treibt diesen externen Pin nicht.

## Bedienansicht: implementiertes Operator-Panel

[TinyCPU_Operator.circ](TinyCPU_Operator.circ) importiert den CPU-Kern und
bietet RESET, STEP und RUN. Setzen Sie RUN und STEP zuerst auf 0, RESET auf 1,
STEP einmal auf 1 und zurück auf 0, danach RESET auf 0. Jeder weitere volle
STEP-Wechsel erzeugt genau eine steigende CPU-Flanke. RUN aktiviert alternativ
den langsamen internen Takt; STEP bleibt dabei auf 0. Die
[Begleitbeschreibung](TinyCPU_Operator.md) und der
[AP-21-Nachweis](../../docs/tiny_cpu_operator_panel_plan.md) erläutern die
Taktarbitrierung und Beobachtungen. Die elektrische Takt- und Kernprüfung ist
implementiert; ein erfolgreiches manuelles Bedienprotokoll steht weiterhin aus.

## Gemeinsame elektrische Abnahme

Der aktuelle [Testleitfaden](../../docs/tiny_cpu_test_guide.md) beschreibt die
Voraussetzungen und alle Bash-/PowerShell-Aufrufe. Unter Bash:

```bash
scripts/test-offline.sh
scripts/test-logisim.sh
```

Das zweite Kommando führt das unterstützte Basisprofil `tinycpu-16-12`,
dynamische INPUT-Fälle, fokussierte Regressionen und Negativkontrollen,
das optionale Peripheriesystem und die Operator-Tests aus. Die vollständige
Matrix ist verpflichtend. `JAVA`, `LOGISIM_JAR` und `LOGISIM_OUTPUT` wählen
Laufzeit und Ausgabeort. Standardziel ist
`artifacts/tinycpu-profile-acceptance/`.

Der [Kernvergleich](../../docs/tiny_cpu_core_trace.md) prüft die Zustände vor
und nach jeder aktiv getriebenen Flanke gegen die VM. Die alte autonome
`table,halt`-Messung bleibt ergänzend; weder deren Zeilenzahl noch das Erreichen
des Halts beweist Zustandsparität. Das Gate meldet den ersten Unterschied mit
Fixture, Flanke, Phase, Signal und Soll-/Istwert.

Die [lokale Abnahme vom 10. November](../../docs/tiny_cpu_input_reset_repair.md)
belegt 63 Kernfixtures, 23 dynamische INPUT-Fälle und die übrigen dort einzeln
aufgeführten Prüfpakete. Der [Funktionsstatus](../../docs/tiny_cpu_instruction_status.md)
nennt die Grenzen. Linux-Nachweis, frische gemeinsame Releaseabnahme und
manuelle GUI-Bedienabnahme bleiben eigene offene Aufgaben.

## Ressourcenverbrauch eingrenzen

Beginnen Sie bei Ladeproblemen mit den drei Smoke-Projekten
[1 Bit](smoke/PinPair-1bit.circ), [12 Bit](smoke/PinPair-12bit.circ) und
[16 Bit](smoke/PinPair-16bit.circ). Danach lassen sich die
[Diagnoseprojekte](diagnostics/) einzeln laden; ihre gleichnamigen `.md`-Dateien
erklären jeweils den Teilkreis. Diese Eingrenzung ersetzt keine Kernabnahme.

## Architektur und verbindliche Regeln

Die [Kernbeschreibung](TinyCPU.md) erklärt die acht Funktionsboxen und ihre
Teilkreise. Der [Systembegleiter](TinyCPU_Peripherals.md) beschreibt die
optionale Integration. Das unterstützte Maschinenformat steht in
[tinycpu-machine-v1.json](tinycpu-machine-v1.json); die laufenden Werkzeuge
stehen in der [Architekturreferenz](../../docs/tiny_cpu.md).

[AGENTS.md](AGENTS.md) schützt die handgezeichneten Decoder, untersagt Tunnel
und verlangt sichtbare Leitungen sowie benannte Schnittstellen. Der
[Benutzerstil](../../docs/tiny_cpu_schematic_style.md) bleibt verbindlich.
Gatterausgänge dürfen nicht direkt zusammengeschaltet werden. Prüfen Sie die
benannten Netze nach jeder Änderung mit:

```bash
python scripts/check-logisim-circuit.py
```

Strukturelle Prüfungen ersetzen weder die elektrische Messung noch eine
Lesbarkeitsprüfung. Die aktuelle Division erhält ausdrücklich die
[v1-Ausnahme −32768 ÷ −1](../../docs/tiny_cpu_compatibility.md).

## Historische Implementierungsschritte

Die früher hier angehängten AP-4-bis-AP-21-Aufbauschritte und alten
Werkzeugaufrufe stehen unverändert im [historischen Protokoll](HISTORY.md).
Sie beschreiben frühere Zustände und dürfen die aktuellen Projektregeln,
Befehle und Abnahmen nicht überschreiben.

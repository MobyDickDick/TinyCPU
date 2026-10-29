# AP 22: Qualitätsbefunde und belastbare Abnahme

**Stand:** 29. Oktober 2026. **Status:** in Bearbeitung; elektrische Abnahme offen.

## Fortschritt am 29. Oktober 2026

22.1 hat jetzt einen verpflichtenden, benannten Pre-/Post-Flankenvergleich
für Minimalkern, AP-5-Countdown und alle 61 bestehenden Matrixfixtures.
Die elektrische Negativkontrolle besteht: Ein verfälschtes Ergebnis wird trotz
Normalhalt erkannt. Die unveränderte Schaltung besteht die neue Abnahme jedoch
nicht: Countdown und 59 der 61 Matrixfixtures weichen ab. Der nächste begrenzte
Reparaturschritt verfolgt ausschließlich `ACC_WRITE_REQUEST` bei
`STORE_ADDRESS`, bevor weitere Fehlerpfade repariert werden. Gültige externe
Eingaben sind mangels öffentlicher Kernpins noch nicht elektrisch prüfbar.
22.1 bleibt deshalb offen. Nachweise stehen im
[Diagnosebericht](tiny_cpu_circuit_debug_report.md#ap-221-elektrischer-kernvergleich-am-29-oktober-2026),
der Vertrag im [Kerntrace-Dokument](tiny_cpu_core_trace.md).

Die Literalpfad-Assertion aus 22.4 wurde als Voraussetzung einer belastbaren
lokalen Suite ebenfalls mit `re.escape()` korrigiert. Die Windows-Suite ist
grün; ein tatsächlicher neuer Linux-CI-Lauf ist noch nicht nachgewiesen.
22.2, 22.3 und 22.5 sind weiterhin offen. Die folgenden Ausgangsbefunde
beschreiben die Bewertung vor diesen Änderungen.

## Anlass und Ausgangsbefunde

Die Projektbewertung am aktuellen Stand hat konkrete Lücken zwischen
Implementierung, dokumentierten Ansprüchen und Abnahmen gefunden. AP 22 sammelt
deren Bearbeitung vor weiteren Funktionserweiterungen. Frühere erfolgreiche
Testläufe bleiben historische Nachweise für die damals ausgeführten Prüfungen;
sie belegen keinen im aktuellen Gate fehlenden Zustandsvergleich.

Die Bewertung hat folgende Befunde geliefert:

- `run_matrix()` in `src/tiny_cpu_logisim.py` ermittelt mit der VM den
  erwarteten Halt und führt die ROM-Fixtures in Logisim aus. `run_trace()`
  prüft Prozessabschluss und nichtleere Tabellenausgabe, vergleicht aber keine
  Rechenergebnisse oder Zwischenzustände gegen die VM. Die dokumentierte
  Kernparität ist damit stärker als die tatsächlich ausgeführte Prüfung.
  `run_system_matrix()` vergleicht dagegen ausgewählte Peripheriezustände
  mit VM-basierten Vektoren; das ist keine vollständige Kernzustandsparität.
- `LOAD_CONST(-32768)` und `DIV_CONST(-1)` ergeben in der VM `-32768` mit
  gesetzter Gültigkeit und ohne Fehlerflag. Das mathematische Ergebnis
  `32768` liegt außerhalb des 16-Bit-Wertebereichs. Die allgemeine
  Architekturbeschreibung verlangt bei arithmetischem Überlauf `OVF` und
  `0 INVALID`; andere Hardwaretexte schließen Divisionsüberlauf aus.
  Dieser Widerspruch muss ausdrücklich aufgelöst werden.
- Die Architekturdokumentation verweist unter anderem auf die fehlenden
  Dateien `tiny_cpu_isa.py`, `tiny_cpu_machine.py`, `tiny_cpu_cli.py` und
  `examples/tiny_cpu/`. Der erste VM-Aufruf im Quickstart erzeugt keinen
  Programmlauf, weil `tiny_cpu_vm.py` keinen CLI-Einstieg besitzt.
- Im lokalen Windows-Lauf bestanden nach Verlegung des temporären
  Verzeichnisses in den Arbeitsbereich 181 von 182 Unit-Tests. Der Test
  `test_missing_vendored_jar_is_named_when_download_fails` verwendet einen
  Windows-Pfad ungequotet als regulären Ausdruck und scheitert an `\U`.

Offline-Konsistenz- und Strukturprüfung bestanden bei dieser Bewertung.
Ein echter elektrischer Logisim-Lauf wurde dabei mangels Java im aktuellen
Suchpfad nicht wiederholt. Die Befunde sind daher kein neuer elektrischer
Defektnachweis für eine konkrete Leitung oder ein bestimmtes Bauteil.

## Offene Aufgaben und Abnahmekriterien

### 22.1 Vollständigen Kernvergleich herstellen — hohe Priorität

- [x] Das tatsächlich beobachtbare Trace-Schema und den Bezug auf steigende
  Taktflanken festlegen. Logisims nur bei Änderungen ausgegebene Tabellenzeilen
  dürfen nicht ungeprüft als Instruktionsschritte gezählt werden.
- [ ] Für das Kernprogramm und alle 61 bestehenden ISA-/Fehler-Fixtures die
  elektrischen Zustände gegen die VM vergleichen: PC, Akkumulator und
  Adressregister samt Gültigkeit, alle Fehlerflags, Ausgabeereignisse mit
  Wert/Gültigkeit sowie Normal- und Fehlerhalt. Speicheränderungen müssen
  Adresse, Wert und Gültigkeit einschließlich anschließenden Lesens abdecken.
- [ ] Eingabefälle mit ausdrücklich festgelegten Werten und Gültigkeit prüfen.
  Unerwartete `E`-/`U`-Werte, fehlende Beobachtungen, zusätzliche oder fehlende
  Instruktionsschritte und abweichende Werte müssen die Abnahme abbrechen.
- [x] Einen gezielt falschen Rechenwert bei weiterhin korrektem Halt in einer
  temporären Schaltungskopie elektrisch nachweisen. Das neue Gate muss diesen
  Fall ablehnen; das Erreichen von `HALT` allein darf ihn nicht bestehen lassen.

**Abnahme:** Das verpflichtende Logisim-Gate verwendet den Vergleich für jede
Fixture. Ein Fehlerbericht nennt Fixture, erste abweichende Flanke, Signal,
Soll- und Istwert und bewahrt die elektrischen Rohdaten auf. Ein unveränderter
korrekter Lauf besteht; der absichtlich falsche Rechenlauf scheitert.

### 22.2 Divisionsüberlauf und arithmetische Grenzen klären — hohe Priorität

- [ ] Den obigen Grenzfall als fokussierte Regression festhalten und das
  Sollverhalten vor einer Implementierungsänderung dokumentieren. Nach dem
  allgemeinen Fehlergrundsatz wäre das Ergebnis `0 INVALID` mit `OVF=1`.
- [ ] Die widersprüchlichen Divisionsverträge abgleichen. Falls die Korrektur
  bislang zugesichertes Version-1-Verhalten ändert, Kompatibilitäts- und
  Versionsfolgen ausdrücklich festhalten.
- [ ] VM und anschließend die kleinste betroffene elektrische Signalkette
  entsprechend korrigieren. Einen Fehler in der Schaltung zuerst elektrisch
  belegen; keine Leitungsänderung allein aus dem VM-Befund ableiten.
- [ ] Alle vier Divisionsadressierungsarten sowie Nullteiler, ungültige
  Operanden, Vorzeichen und Abschneiden gegen null prüfen. Für Addition,
  Subtraktion und Multiplikation die Grenzwerte und unmittelbar außerhalb
  liegende Ergebnisse mit mathematisch festgelegten Erwartungen absichern.
- [ ] Prüfen, dass `CLEAR_ERROR()` Flags löscht, aber ungültige Ergebnisse
  nicht gültig macht. Erwartungswerte dürfen nicht ausschließlich aus der
  zu prüfenden VM selbst abgeleitet werden.

**Abnahme:** Dokumentation, VM und elektrische Grenzfalltests stimmen überein.
Der ursprüngliche Divisionsfall kann nicht mehr unbemerkt als gültiges,
fehlerfreies Ergebnis durchlaufen. Die bestehende ISA-/Peripheriematrix bleibt
unter dem ausdrücklich festgelegten Vertrag grün.

### 22.3 Dokumentation ausführbar und widerspruchsfrei machen — mittlere Priorität

- [ ] Aktuelle Einstiegs- und Referenzseiten von historischen Diagnose- und
  Planungsständen unterscheiden; aktuelle Seiten auf vorhandene Werkzeuge,
  Dateien und tatsächlich implementierte Funktionen ausrichten.
- [ ] Quickstart und Architekturaufrufe in einem frischen Checkout ausführen.
  Für den ersten Programmlauf ein vorhandenes Werkzeug verwenden und Ausgabe
  sowie Exitcode nennen. Fehlende alte CLI-Module nicht nur zur Erfüllung alter
  Verweise nachbauen.
- [ ] Veraltete Aussagen zu Profilen und zum bereits implementierten
  Operator-Panel sowie unzutreffende Behauptungen vollständiger VM-Parität
  korrigieren. Nachweisumfang und offene GUI-Abnahme ausdrücklich benennen.
- [ ] Die zentralen Programmlauf-Beispiele als Regression gegen erwartete
  Ausgabe und Exitcode absichern; lokale Dateilinks der aktuellen Dokumentation
  prüfen. Historische Befehle als solche kennzeichnen.

**Abnahme:** Ein neuer Benutzer kann den dokumentierten ersten Lauf ohne
Korrekturen reproduzieren. Aktuelle Verweise führen zu vorhandenen Dateien;
Funktions- und Abnahmestatus entsprechen den tatsächlich ausgeführten Gates.

### 22.4 Windows-Testfehler beheben — mittlere Priorität

- [x] Im genannten Test Literalpfad und regulären Ausdruck korrekt trennen,
  etwa durch `re.escape()` oder einen direkten Teilstringvergleich.
- [x] Den Download-Fehlerpfad weiterhin gezielt prüfen; die Assertion weder
  entfernen noch den Test unter Windows überspringen.
- [ ] Die vollständige Offline-Suite unter Windows und im bestehenden
  Linux-CI-Umfeld mit dokumentierter Python-Version ausführen.

**Abnahme:** Der bisher fehlerhafte Test besteht auf beiden Plattformen und
erkennt weiterhin eine Fehlermeldung ohne den erwarteten Vendor-Pfad. Die
gesamte Offline-Suite besteht ohne neue Ausnahmen oder übersprungene Tests.

### 22.5 Nachweise und Status neu abnehmen — hohe Priorität, nach 22.1 bis 22.4

- [ ] Offline-Gate, vollständiges elektrisches Kern-/System-Gate und
  Operator-Test auf demselben Kandidaten aus einem frischen Checkout ausführen.
- [ ] Commit, Python-/Java-/Logisim-Versionen, exakte Befehle, Exitcodes und
  Artefaktpfade festhalten; belegte Abdeckung und verbleibende Lücken nennen.
- [ ] Funktionsstatus, Roadmap und Release-Dokumentation anhand dieser
  Nachweise aktualisieren. Den manuellen GUI-Kurztest nur bei tatsächlich
  sichtbarer Bedienung als erledigt markieren, andernfalls offen lassen.

**Abnahme:** Jeder neue Abschlussvermerk verweist auf den tatsächlich
geprüften Commit und seinen Nachweisumfang. Ein grüner Strukturtest oder ein
erreichter Halt wird nicht als vollständige Zustandsparität ausgewiesen.

### 22.6 Eigenständigkeit und Nutzen einordnen — optional

- [ ] Gültigkeitsfortpflanzung und Fehlersemantik mit ausgewählten bekannten
  Ansätzen anhand von Primärquellen vergleichen. Bekannte Prinzipien,
  projektspezifische Kombination und nachgewiesene Vorteile getrennt benennen.
- [ ] Einen konkreten Nutzen mit einem Demonstrator belegen, beispielsweise
  das sichtbare Verfolgen einer ungültigen Berechnung bis zur Ausgabe.

**Abnahme:** Eine kurze Einordnung nennt Quellen, Gemeinsamkeiten,
Unterschiede und Grenzen. Eine Grundlageninnovation oder ein Leistungsgewinn
wird nur bei entsprechendem Nachweis behauptet. Diese Aufgabe ist kein
Blocker für die Fehlerkorrekturen und verlangt keine neue CPU-Architektur.

## Reihenfolge und Grenzen

22.1 schafft die belastbare elektrische Vergleichsbasis für 22.2. Die
mathematischen VM-Grenzfalltests aus 22.2 können vorher beginnen. 22.3 und
22.4 sind unabhängig davon bearbeitbar; 22.5 schließt die Pflichtaufgaben ab.
22.6 bleibt optional. Der oben festgehaltene Teilfortschritt schließt noch
keine elektrische Neuabnahme ab.

Schaltungsänderungen folgen weiterhin dem Fehlernachweis vor der kleinsten
Reparatur und den Regeln in `hardware/logisim/AGENTS.md`. AP 22 erteilt keinen
Auftrag zum Redraw, zur Erweiterung der ISA oder zu einem neuen Hardwareprofil.
Die ursprüngliche Planung und der ausdrücklich belegte Teilfortschritt sind
getrennt dokumentiert; eine erfolgreiche erneute elektrische Abnahme wird
damit weiterhin nicht behauptet.

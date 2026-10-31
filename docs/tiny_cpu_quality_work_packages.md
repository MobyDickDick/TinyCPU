# AP 22: Qualitätsbefunde und belastbare Abnahme

**Stand:** 31. Oktober 2026. **Status:** in Bearbeitung; elektrische Abnahme offen.

## Fortschritt am 31. Oktober 2026: Akkumulatorhalten bei Adressregister-Konstante

Der nächste begrenzte Schritt aus 22.1 ist abgeschlossen. Die passive Messung
bestätigt bei `LOAD_ADDRESS_REGISTER_CONST(20)` vor Flanke 3 fälschlich
`ACC_WRITE_REQUEST=1` und `Datapath.ACC_LOAD=1`. Die lesende Kontaktdiagnose
belegt den direkten `LD_REG_CONST`-Zweig zum vorhandenen `ACC_LOAD_REQUEST`-ODER.
Nur dieser Zweig wurde entfernt und sein Gattereingang auf explizite Null
gelegt; bestehende Bauteile, Pins und übrige Leitungswege blieben unverändert.
Der erweiterte 64-Zeilen-Decodertest prüft die unterdrückte Anforderung und
lehnt eine Kopie mit wiederhergestelltem Fehlerzweig elektrisch ab.

Offline-Verträge, Strukturprüfung, alle 198 Windows-Unit-Tests, beide
identischen Minimalkernläufe, Countdown, die ersten beiden Kernfixtures,
alle sieben Systemfixtures, Operator-Panel und die bisherigen elektrischen
Negativkontrollen bestehen. Der Akkumulator hält an der betroffenen Flanke
jetzt korrekt `7 VALID`. Die serielle Kernmatrix stoppt danach bei derselben
Fixture `load-address-register`, Flanke 3, `post`, `AR`: Soll `20`, Ist `0`.
22.1 bleibt offen; spätere Fixtures wurden gemäß Stop-Regel nicht geöffnet.

Die passive Messung zeigt außerdem ein dauerhaft aktives
`AddressPath.ADDRESS_PATH_STARTUP_RESET`, einen Ladeeingang, der bisher der
Akkumulatoranforderung folgt, und `ADDRESS_IN=1` statt des Operanden `20`.
Diese getrennten Adressregisterpfade wurden nicht mitrepariert. Der nächste
begrenzte Schritt verfolgt zunächst ausschließlich den Resetpfad vom
öffentlichen `RESET` zum benannten Eingang von `AddressPath`, bevor dessen
kleinste belegte Reparatur und erneute Abnahme erfolgen. Befehle, Rohdaten und
Grenzen stehen im
[Diagnosebericht](tiny_cpu_circuit_debug_report.md#ap-221-akkumulatorhalten-bei-adressregister-konstante-am-31-oktober-2026).

## Vorheriger Fortschritt am 30. Oktober 2026: Countdown und Speicherladeauswahl

Der aus CI gemeldete Countdown-Fehler an Flanke 6 ist repariert. Der passive
Flagvergleich führt den falschen `SET_INV` auf die Operandenauswahl zurück:
`CONST_ARGUMENT=1` erreicht `Operations.CONST_OPERAND` nicht, weil dort
`ADDR_REG_ARGUMENT` angeschlossen ist. Außerdem erhält `IMMEDIATE_VALUE` den
RAM-Wert statt des Instruktionsoperanden. Beide Anschlüsse sind nach getrennten
elektrischen Messungen minimal korrigiert. Eine neue verpflichtende Regression
prüft die Countdown-Addition, gültige Null und zwei unabhängige Mutationen von
Selektor und Datenleitung. Der gesamte Countdown besteht jetzt gegen die VM.

Die danach seriell geöffnete Matrix belegte einen separaten Fehler bei
`LOAD_ADDRESS`: `ACC_MEMORY_REQUEST` blieb bei gültigem RAM-Wert aus. Die drei
Eingangszweige des vorhandenen Decoder-ODERs wählen jetzt die drei Speicherlade-
Decodes. Bauteile, Pins und übrige Leitungen blieben erhalten. Der erweiterte
64-Zeilen-Decodertest und die Fixture `load-address` bestehen. Die STORE-
Negativkontrolle prüft weiterhin den unerlaubten Akkumulator-Schreibvorgang;
der konkrete falsche Wert auf dem inaktiven Ladebus wird nun protokolliert,
statt den früher zufälligen Buswert `0` vorauszusetzen.

198 Windows-Unit-Tests, Offline-Verträge, Strukturprüfung, beide identischen
Minimalkernläufe, Countdown, alle sieben Systemfixtures, Operator-Panel sowie
PRINT-/STORE-/Rechenergebnis- und Immediate-Negativkontrollen bestehen. Die
Kernmatrix stoppt nun bei ihrer dritten Fixture `load-address-register` an
Flanke 3, `post`, `ACC`: Soll `7`, Ist `20`. Dort wird
`LOAD_ADDRESS_REGISTER_CONST(20)` ausgeführt; der Trace zeigt außerdem ein
unverändertes Adressregister. Der nächste getrennte Schritt vergleicht zunächst
`LD_REG_CONST`, `ACC_WRITE_REQUEST`, `Datapath.ACC_LOAD` und die Ladeeingänge
von `AddressPath` passiv. Eine vollständige Kernfreigabe wird nicht behauptet.
Die [Nachweise](tiny_cpu_circuit_debug_report.md#ap-221-countdown-operandenauswahl-und-speicherladeanforderung-am-30-oktober-2026)
enthalten alle Zwischenstände und Grenzen.

## Vorheriger Fortschritt am 30. Oktober 2026: PRINT-Weitergabe

Der nächste begrenzte Schritt aus 22.1 ist abgeschlossen. Der passive Vergleich
zeigt `FetchDecodeControls.PRINT=1`, aber `TinyCPUMain.PRINT_ENABLE=0` vor
Countdown-Flanke 5. Die Logisim-API bestätigt, dass die bisherige Leitung am
Kontakt `SET_DIV0` statt an `PRINT` beginnt. Ausschließlich dieser Top-Level-
Zweig ist nun direkt mit `PRINT` verbunden; die Decoderzeichnung blieb
unverändert. Eine neue verpflichtende elektrische Regression prüft positive,
negative und gültige Nullausgaben, aufeinanderfolgende Ereignisse und einen
Lauf ohne PRINT. Ein in einer Kopie unterdrückter Impuls wird trotz Normalhalt
abgelehnt. Der bisherige PRINT-Strukturtest verwendete eine veraltete feste
Portzeile; er löst den Anschluss jetzt anhand der tatsächlichen benannten Pins
auf. Ein zusätzlicher Mutationstest sichert die Offline-Prüfung ab.

Alle 197 Windows-Unit-Tests, Offline-Verträge, Strukturprüfung und die bisherigen
STORE-/Rechenergebnis-Negativkontrollen bestehen. Beide Minimalkernläufe sind
erneut identisch. Der Countdown stimmt bis einschließlich Flanke 5 vollständig
mit der VM überein; der erste Unterschied liegt nun an Flanke 6, `post`, bei
`ERROR_INV`: Soll `0`, Ist `1`. Die Matrix wurde deshalb nicht erneut geöffnet.
Als nächstes wird ausschließlich die Erzeugung und Übernahme von
`ErrorFlags.SET_INV` um diese Flanke passiv verfolgt. AP 22.1 bleibt offen.
Befehle, Rohdaten und Grenzen stehen im
[PRINT-Diagnoseabschnitt](tiny_cpu_circuit_debug_report.md#ap-221-print-weitergabe-am-30-oktober-2026).

## Vorheriger Fortschritt am 30. Oktober 2026: STORE_ADDRESS

Der begrenzte Reparaturschritt für `ACC_WRITE_REQUEST` bei `STORE_ADDRESS`
ist abgeschlossen. Der elektrisch belegte direkte Zweig von `STORE_ADR`
zum ODER `ACC_LOAD_REQUEST` wurde entfernt; eine explizite Null hält den
freigewordenen Eingang definiert, ohne das Gatter oder seine übrigen Anschlüsse
zu verschieben. Der erweiterte Decodertest und der neue verpflichtende
`scripts/test-logisim-store.py` sichern gültiges Speichern mit `-1` und `0`
sowie die Ablehnung einer absichtlich wieder aktivierten Ladeanforderung ab.
Offline-Verträge, Strukturprüfung und alle 196 Windows-Unit-Tests bestehen.

Der erneut ausgeführte Countdown stimmt nun bis einschließlich Flanke 4
vollständig mit der VM überein. Sein erster Unterschied liegt an Flanke 5,
`pre`, bei `PRINT_ENABLE`: Soll `1`, Ist `0`. Der nächste begrenzte Schritt
verfolgt ausschließlich den dortigen `PRINT`-Decode bis zum öffentlichen
Ausgabe-Enable; erst ein benannter erster Unterschied darf eine Reparatur
auslösen. Eine zusätzliche Diagnose mit ungültigem Akkumulator zeigt weiterhin
ein fehlendes `INV`-Flag beim Speichern und bleibt als separater Befund offen.
Die gesamte Matrix wurde nach dem roten Countdown gemäß Stop-Regel nicht
erneut geöffnet; die 59 Abweichungen unten sind die Bestandsaufnahme vom
29. Oktober, keine neue Zählung. 22.1 bleibt offen. Reproduktion und Grenzen
stehen im [neuen Diagnoseabschnitt](tiny_cpu_circuit_debug_report.md#ap-221-store_address-ladeanforderung-am-30-oktober-2026).

## Fortschritt am 29. Oktober 2026

22.1 hat jetzt einen verpflichtenden, benannten Pre-/Post-Flankenvergleich
für Minimalkern, AP-5-Countdown und alle 61 bestehenden Matrixfixtures.
Die elektrische Negativkontrolle besteht: Ein verfälschtes Ergebnis wird trotz
Normalhalt erkannt. Die unveränderte Schaltung besteht die neue Abnahme jedoch
nicht: Countdown und 59 der 61 Matrixfixtures weichen ab. Der damals nächste
begrenzte Reparaturschritt für `ACC_WRITE_REQUEST` bei `STORE_ADDRESS` ist
oben mit seinem neuen Nachweisstand fortgeschrieben. Gültige externe
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

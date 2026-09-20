# Bedienbarkeitsbefund und Vorschlag für ein TinyCPU-Operator-Panel

**Status:** dokumentierter Folgepaket-Vorschlag, noch nicht umgesetzt.

## Anlass

Die elektrische 16/12-TinyCPU ist über automatische Offline- und
Simulatorprüfungen umfangreich nachweisbar, aber ihre aktuelle
Logisim-Hauptseite ist keine selbsterklärende Bedienoberfläche. `TinyCPUMain`
ist eine Integrationsgrenze mit externen Eingängen für `CLK` und `RESET`.
Automatische Läufe erzeugen deshalb eine temporäre Kopie und ersetzen diese
Eingänge durch autonome Testtreiber. Ein Mensch muss dagegen derzeit den
Resetpegel und jede Taktflanke mit dem Poke-Werkzeug erzeugen und zahlreiche
technische Pins unmittelbar auswerten.

Der abgebrochene AP-20.8-Bedienversuch hat diese Lücke sichtbar gemacht. Die
beobachteten Anzeigen `U` und `E` waren unbekannte beziehungsweise elektrische
Fehlerwerte und kein regulärer Fehlerhalt. Das ist kein Beleg gegen die bereits
bestandenen automatischen Schaltungsnachweise; es belegt jedoch, dass zwischen
elektrischer Prüfbarkeit und menschlicher Bedienbarkeit unterschieden werden
muss.

## Festgestellte Bedienhürden

- Auf `TinyCPUMain` fehlen unmittelbar verständliche Schaltflächen für Reset,
  Einzelschritt und Start/Stopp.
- Der Logisim-Menübefehl für einen manuellen Clock-Zyklus taktet keinen
  externen `CLK`-Eingang; ein Bediener muss `CLK` stattdessen selbst von `0`
  auf `1` und zurück auf `0` schalten.
- Die Pins zeigen rohe Logikzustände. Ohne zusätzliche Legende sind ein
  gesetztes Bit (`1`), ein unbekannter Wert (`U`) und ein elektrischer
  Fehlerwert (`E`) leicht zu verwechseln.
- Programmzähler, aktueller Befehl, Akkumulator, Ausgabe, Haltursache und die
  sechs Fehlerflags sind nicht zu einer lesbaren Bedienansicht gruppiert.
- Der Normalhalt- und der Fehlerhaltfall benötigen unterschiedliche
  ROM-Inhalte, ohne dass eine sichere Demonstrationsauswahl angeboten wird.
- Die automatische Testbarkeit kann deshalb einen erfolgreichen manuellen
  Erstkontakt nicht ersetzen.

## Zielbild eines getrennten Operator-Panels

Ein späteres, eigenständig abgegrenztes Arbeitspaket soll ein Blatt wie
`TinyCPUOperator` oder ein separates Demonstrationsprojekt ergänzen. Es bindet
den geprüften CPU-Kern ein, ohne `TinyCPUMain`, seine Netze oder die
ISA-Verträge optisch beziehungsweise elektrisch umzubauen.

Das minimale Panel enthält:

| Element | Erwartetes Verhalten |
|---|---|
| `RESET` | erzeugt einen eindeutigen vollständigen Resetimpuls |
| `STEP` | erzeugt genau eine vollständige CPU-Taktperiode |
| `RUN` | schaltet einen langsamen, sichtbaren automatischen Takt ein und aus |
| Taktanzeige | zeigt Pegel und Flanken des tatsächlich verwendeten CPU-Takts |
| PC- und Befehlsanzeige | zeigt Program Counter, Befehlswort und möglichst den decodierten Befehlsnamen |
| Akkumulatoranzeige | zeigt Wert und Gültigkeit getrennt |
| Ausgabeanzeige | zeigt `PRINT_VALUE` nur zusammen mit Enable und Validität |
| Haltanzeigen | unterscheidet Normalhalt und regulären Fehlerhalt farblich und textlich |
| Fehlerübersicht | benennt alle sechs Fehlerflags statt nur rohe Bits zu zeigen |
| Zustandslegende | erklärt mindestens `0`, `1`, `U` und `E` unmittelbar im Panel |

Als Komfortumfang sind ein geladenes Countdown-Demoprogramm, eine getrennte
Fehlerhalt-Demonstration und eine kleine Historie der sichtbaren Ausgaben
`3, 2, 1` sinnvoll. Der Normalbetrieb soll für einen neuen Benutzer auf
**Reset drücken, Step drücken, Ausgabe ansehen** reduzierbar sein.

## Abgrenzung

Der Vorschlag ändert weder Opcode-Belegung noch Daten- oder Adressbreiten. Er
ersetzt auch keine elektrische Regression und darf nicht zur Umzeichnung von
`FetchDecodeControls` oder `TinyCPUMain` verwendet werden. Bedienlogik,
Demonstrations-ROM und Anzeigen gehören auf die neue Bediengrenze. Der bereits
geprüfte Kern bleibt die einzige Quelle der angezeigten CPU-Zustände.

Das Operator-Panel ist außerdem **kein nachträglicher Ersatz für den aktuell
als nicht durchgeführt markierten AP-20.8-GUI-Kurztest**. Erst nach seiner
eigenen Implementierung und Prüfung kann ein sichtbar und manuell bedienter
Lauf auf dem Panel als neuer GUI-Nachweis protokolliert werden.

## Abnahmekriterien für ein späteres Arbeitspaket

1. Ein neuer Benutzer kann das Countdown-Programm anhand einer höchstens
   einseitigen Kurzanleitung resetten, schrittweise ausführen und bis zum
   Normalhalt beobachten.
2. Jeder Druck auf `STEP` erzeugt nachweislich genau eine steigende CPU-Flanke;
   gehaltene oder prellende Bedieneingaben erzeugen keine zusätzlichen
   Instruktionsschritte.
3. `RUN` und `STEP` können den Takt nicht gleichzeitig mehrfach treiben.
4. Die sichtbaren Ausgaben lauten `3`, `2`, `1`; danach wird ausschließlich
   Normalhalt angezeigt.
5. Eine getrennte Demonstration erreicht den regulären Fehlerhalt als
   boolesche `1`, ohne `U` oder `E` als Erfolg zu akzeptieren.
6. Reset stellt PC, Haltanzeigen und Fehlerübersicht reproduzierbar auf den
   dokumentierten Ausgangszustand zurück.
7. Strukturtests sichern eindeutige Takt- und Resettreiber sowie die Breiten
   aller sichtbaren Busse; elektrische Tests vergleichen den Bedienlauf mit
   demselben Referenzmodell wie die bestehende Profilabnahme.
8. Der bestehende Offline- und elektrische Prüfablauf von `TinyCPUMain` bleibt
   unverändert grün.

## Dokumentationsfolge

Bei einer Umsetzung werden die Kurzanleitung in
`hardware/logisim/README.md`, der Funktionsstatus und der Diagnosebericht um
den tatsächlich beobachteten Bedienlauf ergänzt. Bis dahin bleibt dieses
Dokument bewusst ein Vorschlag und behauptet keine vorhandene Bedienoberfläche.

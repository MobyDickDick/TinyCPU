# Gemeinsamer Zeichenstil für Elektroschemas

Benutzerwunsch vom 1. November 2026, einschließlich der Ergänzung
„so wenig Konstanten wie möglich“. Dieses Dokument hält die Gestaltungsregeln
für weitere Bearbeitungen fest. Es ist ein Arbeitspaket im bestehenden TinyCPU-
Projekt; ein separates CPU-Projekt ist dafür nicht erforderlich.

Bauteilbeschriftungen erhalten gemäß Benutzerwunsch vom 8. November 2026
mindestens 10 Punkt Schriftgröße. Insbesondere dürfen sie nicht durch eine
Schriftgröße von 1 Punkt praktisch unsichtbar gemacht werden.

Seit dem Benutzerauftrag vom 9. November 2026 verwenden alle Funktionsboxen
die von Logisim erzeugte Darstellung `logisim_evolution`. Eigene Symbolformen
und `appear`-Zeichnungen sind damit ersetzt. Die vorhandenen fachlichen Namen
und elektrischen Schnittstellen bleiben erhalten; geänderte Standardanschlüsse
werden nach Signalnamen verbunden und nativ geprüft. Die Vierergruppen der
äußeren Blattpins bleiben auf ausdrücklichen Benutzerwunsch erhalten, auch
wenn dafür breitere Anschlussauffächerungen erforderlich sind. Die dichten,
von Logisim fest vorgegebenen Symbolanschlüsse werden nur im Anschlussbereich
aufgefächert. Der Schutz beider Decoderzeichnungen gilt weiterhin.

Die [Leitungskontrolle vom 10. November](tiny_cpu_wire_review_20261110.md)
prüft lange parallele Leitungen zusätzlich unabhängig von der Layoutreferenz.
Zusammenhängende Abschnitte werden auch über explizite Abzweigpunkte hinweg
gezählt: Überlappen parallele Läufe über mehr als 160 Pixel, bleibt mindestens
eine Rasterreihe frei. Die 160-Pixel-Grenze der automatischen Prüfung ist keine
Erlaubnis für beliebige enge Leitungen; kurze Auffächerungen bleiben auf die
festen Bauteilanschlüsse beschränkt. Beide geschützten Decoder bleiben ausgenommen.

ODER-Eingänge werden von der Eingangsseite angefahren: bei nach rechts
gerichteten Gattern endet die Leitung von links waagrecht am Pin. Abzweige
liegen vor dem Pin; Leitungen dürfen nicht hinter den Eingang zurücklaufen.
Die [Korrektur und Prüfung vom 8. November](tiny_cpu_or_inputs_20261108.md)
dokumentiert die betroffenen Auffächerungen.

Die anschließende [Fortsetzung nach der handbereinigten OR-Schaltung](tiny_cpu_author_style_followup_20261108.md)
verwendet die aktuellen Benutzerzeichnungen bis einschließlich
`OrArithmeticCircuit` als Referenz und prüft die 34 nachfolgenden Kernblätter.

## Präzisierung vom 8. November 2026: Gatterabstand und Rückführungsrichtung

Die zwei Punktreihen Freiraum gelten auch an einzelnen AND-/OR-Gliedern und
Registern. Gemessen wird zur tatsächlichen äußeren Symbolkante, nicht nur
zum Anschlusspunkt oder zu einer Funktionsbox. Gerade eigene Anschlussstücke
dürfen bis zum Pin reichen. Beschriftungen erhalten zusätzlich freie Flächen;
weder Eingangsleitungen noch Rückführungen dürfen sie überzeichnen.

Rückführungen sind vom Ausgang aus im Gegenuhrzeigersinn zu zeichnen. Bei
einer von links nach rechts angeordneten Speicherzelle führt der Weg vom
Q-Ausgang nach rechts, nach oben und oberhalb der Logik nach links zurück.
Der obere Korridor muss auch Register- und Gatterbezeichnungen freihalten.
Der Schutz des handgezeichneten Decoders bleibt bestehen.
Die konkrete Korrektur beider `ErrorFlags`-Fassungen und ihre nativen
Nachweise stehen im [ErrorFlags-Layoutbericht](tiny_cpu_errorflags_layout_20261108.md).
Die Korrektur der Gatterabstände und des linken INPUT_VALID-Verteilers in
beiden MUL-Fassungen steht im [MUL-Layoutbericht](tiny_cpu_mul_layout_20261108.md).
Die anschließende elektrische Korrektur der MUL-Symbolanschlüsse in
`Operations` ist im [Operations-Bericht](tiny_cpu_operations_repair_20261108.md)
mit integrierten CPU- und Arithmetikprüfungen dokumentiert.

## Präzisierung vom 8. November 2026: strikt kompakte Anschlusskorridore

Der Benutzer hat den ersten Durchgang anhand zweier Ansichten von
`CPUAddressUnitLink` als noch zu großzügig korrigiert. Maßgeblich ist die
zweite, kompaktere Ansicht: Busabgriffe möglichst direkt auf die Anschlusszeilen
legen, unnötige Höhenversätze entfernen und Ausgangsbusse an die Box heranführen.
Freie Korridore werden bis zum tatsächlich benötigten Platz verkürzt. Pauschale
Restabstände von 80 oder 100 Pixeln sind kein Gestaltungsziel. Auch ein festes
Modulo-Raster rechtfertigt keine künstliche Verlängerung eines übersichtlichen
Signalwegs. Die wirklichen Leitungslücken und der 20-Pixel-Freiraum der Boxen
bleiben verbindlich. Native Symbolgrößen, Anschlussbelegung und geschützte
Decoderzeichnungen bleiben erhalten.
Native Vorher-/Nachher-Ansichten und Nachweise stehen im
[Bericht zur strikten Verdichtung](tiny_cpu_strict_layout_20261108.md).

## Präzisierung vom 8. November 2026: übrige Blätter an TinyCPUMain angleichen

Der Benutzer hat die Überarbeitung der übrigen Schaltschemen ausdrücklich
beauftragt: möglichst wenige Kreuzungen, kurze Leitungen und mindestens zwei
Punktreihen Abstand zu Funktionsboxen. Bei Logisims 10-Pixel-Raster bedeutet
das mindestens 20 Pixel für parallel an einer Box vorbeigeführte Leitungen
und für den ersten Knick einer Anschlussleitung. Die geraden Anschlussstücke
führen selbstverständlich bis zum jeweiligen Pin. Freie Leitungskorridore
werden vor dem Verkürzen berücksichtigt; die vorhandenen Funktionsgruppen
bleiben erkennbar. `TinyCPUMain` dient als Referenz.

Dieser konkrete Auftrag erlaubt die unten zuvor ausgeschlossene Überarbeitung
der übrigen bestehenden Blätter. Der Schutz beider `FetchDecodeControls`-
Zeichnungen bleibt bestehen. Die neuen exakten Geometrien werden erst nach
nativem Anschlussvergleich und Sichtkontrolle in der Layoutreferenz nachgeführt.
Umfang, native Ansichten und Prüfergebnisse stehen im
[Layoutbericht vom 8. November](tiny_cpu_remaining_layout_20261108.md).

## Präzisierung vom 7. November 2026: bestehende Zeichnung erhalten

Der Benutzer hat die großflächige Umzeichnung vom 6. November anhand des
Vorher-/Nachher-Bildes ausdrücklich zurückgewiesen. Die vorherige Anordnung
und Leitungsführung wurden deshalb [wiederhergestellt](tiny_cpu_layout_restoration_20261107.md).
Bei bestehenden Blättern hat die Nähe zu dieser gestalteten Referenz Vorrang
vor einer automatischen Neuanordnung zur Erfüllung eines starren Koordinatenrasters.
Die unten genannten Abstände bleiben Gestaltungsziele für neue und lokal
ergänzte Zeichnungsteile; sie sind kein Auftrag, bestehende Blätter erneut
großflächig umzubauen. Elektrische Fehler werden weiter möglichst lokal behoben.

Die wiederhergestellten Geometrien sind in
`hardware/logisim/layout-restoration-v1.json` festgehalten. Nur diese exakten
Zeichnungen sind von der bisherigen Modulo-Rasterprüfung ausgenommen;
Verbindungs-, Schnittstellen-, Tunnel- und elektrische Prüfungen bleiben aktiv.
Eine geänderte Leitung oder Bauteilposition hebt die betreffende Ausnahme auf.
Nach einem notwendigen lokalen Eingriff ist die Referenz nach elektrischem
Verbindungsvergleich und nativer Sichtkontrolle nachzuführen; die Rastermeldung
rechtfertigt keine erneute großflächige Umzeichnung.
Eine bestandene Prüfung ersetzt weiterhin keine Beurteilung der Lesbarkeit.

## Ziel und Geltungsbereich

Eine Zeichnung ist gut lesbar, wenn man Eingänge findet, ihre Verarbeitung von
oben nach unten und von links nach rechts verfolgen und die Ausgänge erkennen
kann, ohne ständig lange Leitungen mit dem Finger nachfahren zu müssen. Regelmäßige Abstände allein
reichen dafür nicht aus. Die Regeln gelten für Übersicht, Funktionsboxen,
Teilkreise, Peripherie, Operator-Panel, Diagnose- und Smoke-Schaltungen sowie
für künftig hinzukommende Schemas.

Der handgezeichnete `FetchDecodeControls` bleibt gemäß
[`hardware/logisim/AGENTS.md`](../hardware/logisim/AGENTS.md) geschützt,
einschließlich seiner Diagnosefassung. Dieser allgemeine Gestaltungswunsch
ist kein Auftrag, die geschützte Zeichnung neu anzuordnen.

## Pins und Gruppen

- Eingänge stehen auf der linken Seite, beginnend oben. Ausgänge stehen auf
  der rechten Seite, ebenfalls beginnend oben. Beide Spalten haben möglichst
  eine gemeinsame obere Ausgangshöhe. Pins werden nicht über das ganze Blatt
  verstreut, nur um sie auf die Höhe eines weit entfernten Bauteils zu bringen.
- Innerhalb einer Seite bilden höchstens vier Objekte eine Gruppe. Ein Objekt
  kann ein Einzelpin oder eine erkennbare zusammengehörige Pingruppe sein;
  ein Busanschluss zählt als ein Objekt, nicht nach seiner Bitbreite.
- Zwischen zwei Vierergruppen bleibt zusätzlich der Platz eines Einzelpins
  frei. Die letzte Gruppe darf weniger als vier Objekte enthalten.
  Pinbeschriftungen und mehrzeilige Busanzeigen benötigen eigenen Platz.
- Fachlich zusammengehörige Signale bleiben zusammen. Ihre Reihenfolge soll
  die Verarbeitung erklären; eine rein alphabetische Sortierung ist kein Ziel.
- Pinleitungen beginnen und enden waagrecht. Anpassungen an feste
  Bauteilanschlüsse bleiben kurz und liegen nahe an den betreffenden Bauteilen.
- Die Blattposition eines Pins und seine Position am eingebetteten Symbol
  sind getrennte Dinge. Bestehende Symbolanschlüsse, Richtungen, Namen,
  Bitbreiten und Busbelegungen bleiben kompatibel; explizite `circ-port`-
  Bindungen müssen beim Verschieben ihrer Blattpins mitgeführt werden.

## Leitungen und Bauteile

- Zwischen parallelen Leitungen bleibt mindestens eine Rasterzeile frei.
  Bei 10 Pixel Rasterweite bedeutet das mindestens 20 Pixel Spurabstand.
- Nach höchstens vier parallelen Leitungen bleiben drei Rasterzeilen frei:
  mindestens 40 Pixel Abstand von der letzten Spur zur nächsten Gruppe.
  Das gilt horizontal und vertikal.
- Nicht jede fachliche Verbindung ergibt ein vollständiges Viererbündel.
  In solchen Bereichen werden die tatsächlich vorhandenen horizontalen
  Leitungen von oben und die vertikalen von links gezählt; nach jeweils
  vier Leitungen folgt die größere Lücke. Fehlende Leitungen werden nicht
  durch zusätzliche Signale oder künstliche Umwege ergänzt.
- Die bisher verwendeten langen Spuren bei 20/40/60/80 modulo 100 erfüllen
  diese Abstände. Das Raster ist ein Hilfsmittel, keine ausreichende
  Bewertung der gesamten Zeichnung.
- Der Daten- und Signalfluss läuft möglichst von oben nach unten und von
  links nach rechts. Bauteile werden
  nach ihrem Zusammenhang platziert, bevor die Leitungen geführt werden.
  Zusammengehörige Auswahl- oder Verarbeitungsstufen stehen nahe beieinander.
- Auf der rechten Seite dürfen Ausgangsleitungen wieder nach oben zu den
  oben angeordneten Daten- und Ausgangspins geführt werden. Diese Rückführung
  erhält einen eigenen, gut verfolgbaren Korridor.
- Für `TinyCPUMain` ist diese Flussrichtung wegen der vielen Verbindungen
  zwischen Funktionsboxen derzeit nicht durchgehend erreichbar; die Übersicht
  ist eine ausdrückliche Ausnahme. Auch feste Anschlüsse einzelner Bauteile,
  insbesondere Multiplexer, dürfen kurze lokale Gegenrichtungen erfordern.
  Diese Ausnahmen rechtfertigen keine unnötigen Umwege in der übrigen Logik.
- Leitungen sind sichtbar und rechtwinklig. Sie sollen kurz sein, wenige
  Knicke und möglichst wenige Kreuzungen haben. Eine geringfügig längere,
  klar verfolgbare Leitung ist besser als eine schwer erkennbare Abkürzung.
- Leitungen dürfen keine unbeteiligten Symbole, Beschriftungen oder Anschlüsse
  durchqueren. Abzweige und bloße Kreuzungen müssen unterscheidbar bleiben.
- Rückführungen erhalten einen erkennbaren freien Korridor am Rand der
  zugehörigen Logik. Große leere Schleifen quer über das Blatt vermeiden.
- Wo immer es die Darstellung vereinfacht, werden zusammengehörige Signale
  in physisch verdrahteten Bussen zusammengefasst. Die Aufteilung erfolgt
  nahe an den Quellen und Zielen; Busbreite und Bitbelegung werden eindeutig
  dokumentiert. Splitter zeigen zu ihren angeschlossenen Signalen; die
  Bitzuordnung bleibt erhalten. Tunnel sind im gesamten Projekt verboten.
- Feste enge Anschlussreihen dürfen lokal aufgefächert werden. Diese Ausnahme
  gilt nur unmittelbar am Bauteil und rechtfertigt keine engen langen Bündel.

## Möglichst wenige Konstanten

- Jede Konstante braucht einen elektrischen Zweck: beispielsweise ein fester
  Auswahlwert, eine Bereichsgrenze oder ein notwendiger definierter Ruhepegel.
  Keine zusätzlichen Konstanten allein für ein regelmäßigeres Bild einfügen.
- Unbenutzte oder nachweislich überflüssige Konstanten entfernen. Gleicher
  Wert und gleiche Breite machen zwei Konstanten zunächst nur zu Kandidaten
  für eine gemeinsame Versorgung, nicht automatisch zu einem Fehler.
- Gleichwertige feste Werte innerhalb desselben Teilkreises möglichst aus
  einer gemeinsamen Quelle versorgen, wenn ihre Verteilung übersichtlich
  bleibt. Getrennte kurze lokale Quellen dürfen bestehen bleiben, wenn eine
  zentrale Quelle lange Rückführungen oder viele Kreuzungen erzeugen würde.
- Keine Dummy-Konstanten für unnötige Gattereingänge ergänzen. Wo eine
  Verringerung der Eingangszahl sinnvoll erscheint, ist das eine gesondert
  elektrisch zu prüfende Logikänderung, keine reine Layoutänderung.
- Konstanten nicht durch offene Eingänge oder zufällig passende Laufzeitsignale
  ersetzen. Unterschiedliche Breiten, Werte oder elektrische Rollen nicht
  ungeprüft zusammenlegen. Die Anzahl darf nicht durch Verstecken in neuen
  Hilfsboxen oder durch Tunnel nur scheinbar sinken.

## Priorität bei Zielkonflikten

1. Elektrische Funktion, eindeutige Verbindungen und kompatible Schnittstellen.
2. Verständliche Leserichtung, fachliche Gruppen und erkennbare Signalwege.
3. Pinanordnung, freie Leitungsspuren und möglichst wenige Kreuzungen.
4. Kurze Leitungen, wenige Knicke, wenige Konstanten und kompakte Fläche.

„Möglichst“ erlaubt begründete lokale Ausnahmen. Es erlaubt nicht, den
grundsätzlichen Stil zu ignorieren. Die beste Zeichnung ist nicht zwangsläufig
die mit den wenigsten Pixeln oder Bauteilen.

## Bearbeitung und Abnahme

Vor einer Umzeichnung den eingehenden Stand sichern, einschließlich lokaler
Benutzeränderungen. Einen Teilkreis nach dem anderen bearbeiten, seine echten
Netze erhalten und Vorher-/Nachher-Ansichten aus Logisim vergleichen. Eine
stilistische Referenz soll ein echter verdrahteter Schaltplan sein, keine nur
ähnlich aussehende Illustration. Das im Chat gezeigte `AccumulatorUnit` ist
ein geeigneter erster Referenzfall.

Pro bearbeitetem Teilkreis prüfen:

- Beginnen Eingänge links oben und Ausgänge rechts oben? Sind die Vierergruppen
  und ihre freien Zwischenräume sichtbar?
- Lassen sich die wesentlichen Signalwege ohne langes Suchen verfolgen?
  Gibt es vermeidbare Kreuzungen, Umwege oder Leitungen durch Beschriftungen?
- Folgt die Verarbeitung möglichst der Richtung oben nach unten und links
  nach rechts? Bleibt das Hochführen der Ausgänge am rechten Rand erkennbar?
- Sind die Leitungslücken auch an Abzweigen noch erkennbar?
- Hat jede verbliebene Konstante einen nachvollziehbaren Zweck? Würde eine
  Zusammenlegung die Zeichnung tatsächlich verbessern?
- Stimmen Netze, Bitbreiten, Busbelegung und Symbolanschlüsse weiterhin?

Layoutänderungen brauchen einen positionsunabhängigen Verbindungsvergleich,
die vorhandenen Strukturprüfungen und passende elektrische Regressionen.
Eine Konstantenzusammenlegung verändert die Zahl der Quellen und kann deshalb
einen bisherigen Topologie-Fingerabdruck ändern; dessen Erwartungswert darf
nicht ohne eigenständigen Nachweis des unveränderten Verhaltens ersetzt werden.
Abweichungen und noch unbearbeitete Schaltungen ausdrücklich offen führen.

## Projektweiter Durchgang vom 6. November 2026

Die [projektweite Überarbeitung](tiny_cpu_circuit_repair_20261106.md) erfasst
24 Dateien mit 58 Definitionen: 56 überarbeitet, beide geschützten Decoder
bytegleich erhalten. Die tatsächliche Eingangsbasis dieses Durchgangs enthält
63 Konstanten, der korrigierte Stand 59. Native Ansichten und Kontaktvergleiche
sowie elektrische Grenzfall-, Kern- und Operatorprüfungen sichern die Änderungen.
Die folgenden Zahlen und offenen Blätter beschreiben den historischen Teilstand.

## Stand vom 1. November 2026

Die Regeln sind dauerhaft im Projekt hinterlegt. Die frühere Überarbeitung in
[`tiny_cpu_readable_wiring.md`](tiny_cpu_readable_wiring.md) ist ein historischer
Teilstand für acht Funktionsboxen und keine Abnahme sämtlicher Schemas nach
diesem vollständigen Stil.

Die Bestandsaufnahme findet 24 `.circ`-Dateien mit 56 Teilkreisdefinitionen
(einschließlich separat gespeicherter Diagnosefassungen), insgesamt 64
Konstanten. Davon stehen 29 im Kernprojekt, sieben im Operator-Panel, fünf im
Peripherieprojekt und 23 in den Diagnoseprojekten. Diese Zahlen sind eine
Ausgangsbasis, kein Urteil darüber, welche Konstanten entfallen können.
Die geschützte Decoder-Diagnose enthält davon sechs Konstanten.

Ein erster praktischer Durchgang überarbeitet `AccumulatorUnit`, `BranchUnit`
und `ExecutionUnit` mit oben beginnenden Pingruppen und zusätzlichen sichtbar
verdrahteten Signalbussen. Vorher-/Nachher-Ansichten, Busbelegungen und die
elektrischen Nachweise stehen in
[`tiny_cpu_schematic_reference.md`](tiny_cpu_schematic_reference.md).
Die übrigen 53 Teilkreisdefinitionen und die projektweite Bewertung
entfernbarer Konstanten sind noch offen. Eine vollständige visuelle Abnahme
sämtlicher Schemas ist damit weiterhin nicht erfolgt.

Der anschließende [Nachtrag](tiny_cpu_schematic_followup.md) erhält die vom
Benutzer erneut angepasste Akkumulator-Anordnung, ergänzt die Notizen und
prüft die Funktion. Kurze Grundbeschreibungen stehen nun neben allen
24 `.circ`-Dateien für sämtliche 56 Teilkreisdefinitionen.

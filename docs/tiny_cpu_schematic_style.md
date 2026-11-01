# Gemeinsamer Zeichenstil für Elektroschemas

Benutzerwunsch vom 1. November 2026, einschließlich der Ergänzung
„so wenig Konstanten wie möglich“. Dieses Dokument hält die Gestaltungsregeln
für weitere Bearbeitungen fest. Es ist ein Arbeitspaket im bestehenden TinyCPU-
Projekt; ein separates CPU-Projekt ist dafür nicht erforderlich.

## Ziel und Geltungsbereich

Eine Zeichnung ist gut lesbar, wenn man Eingänge findet, ihre Verarbeitung von
links nach rechts verfolgen und die Ausgänge erkennen kann, ohne ständig lange
Leitungen mit dem Finger nachfahren zu müssen. Regelmäßige Abstände allein
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
- Die bisher verwendeten langen Spuren bei 20/40/60/80 modulo 100 erfüllen
  diese Abstände. Das Raster ist ein Hilfsmittel, keine ausreichende
  Bewertung der gesamten Zeichnung.
- Die Verarbeitung läuft möglichst von links nach rechts. Bauteile werden
  nach ihrem Zusammenhang platziert, bevor die Leitungen geführt werden.
  Zusammengehörige Auswahl- oder Verarbeitungsstufen stehen nahe beieinander.
- Leitungen sind sichtbar und rechtwinklig. Sie sollen kurz sein, wenige
  Knicke und möglichst wenige Kreuzungen haben. Eine geringfügig längere,
  klar verfolgbare Leitung ist besser als eine schwer erkennbare Abkürzung.
- Leitungen dürfen keine unbeteiligten Symbole, Beschriftungen oder Anschlüsse
  durchqueren. Abzweige und bloße Kreuzungen müssen unterscheidbar bleiben.
- Rückführungen erhalten einen erkennbaren freien Korridor am Rand der
  zugehörigen Logik. Große leere Schleifen quer über das Blatt vermeiden.
- Physisch verdrahtete Busse dürfen zusammengehörige Signale bündeln. Splitter
  zeigen zu ihren angeschlossenen Signalen; die Bitzuordnung bleibt erhalten.
  Tunnel sind im gesamten Projekt verboten.
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

Die projektweite Umzeichnung und die elektrische Bewertung entfernbarer
Konstanten sind noch offen. Beim Festhalten dieser Regeln wurden keine
Schaltungsdateien geändert; insbesondere sind noch keine neue Referenzzeichnung
und keine vollständige visuelle Abnahme entstanden.

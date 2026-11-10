# Verbindliche Struktur der CPU-Übersicht

`TinyCPUMain` ist ausschließlich eine Übersicht aus fachlich benannten
Funktionsboxen, öffentlichen Anschlusspins und deren Leitungen. Einzelne
Gatter, Multiplexer, Splitter, Konstanten, Register, RAMs und Probes
gehören in die zuständigen Teilkreise. Neue Fehlerkorrekturen dürfen diese
Abstraktionsgrenze nicht wieder auflösen. Diagnoseanzeigen gehören in eine
eigene Diagnosebox. Steuersignale dürfen als benannter, dokumentierter Bus
zwischen Funktionsboxen geführt und ausschließlich darin aufgeteilt werden.

# Projektweites Tunnelverbot

Auf ausdrücklichen Benutzerwunsch vom 1. November 2026 sind **keine Tunnel**
zulässig, auch nicht innerhalb von Funktionsboxen, in Diagnoseschaltungen
oder als Ausnahme für lange Rückführungen. Alle Verbindungen müssen als
sichtbare, rechtwinklige Leitungen oder physisch verdrahtete Busse mit
Splittern ausgeführt sein. Diese Regel ersetzt alle älteren
Tunnel-Ausnahmen in der Projektdokumentation. Der Offline-Verifikator muss
Tunnel-Komponenten in jeder `.circ`-Datei ablehnen.

# Verbindliche Lesbarkeitsregeln

Der vollständige Benutzerstil für alle Schaltpläne steht in
[`docs/tiny_cpu_schematic_style.md`](../../docs/tiny_cpu_schematic_style.md).
Seit dem 1. November 2026 gilt ergänzend:

- Eingänge beginnen links oben, Ausgänge rechts oben. Je höchstens vier
  Pinobjekte oder fachliche Pingruppen bilden eine Gruppe; zwischen den
  Gruppen bleibt zusätzlich der Platz eines Einzelpins frei.
- Die obere Anordnung und erkennbare Gruppierung haben Vorrang vor einer
  bloßen Ausrichtung aller Blattpins auf weit entfernte Signalquellen.
- Daten und Signale fließen nach Möglichkeit von oben nach unten und von
  links nach rechts. Rechts dürfen Ausgabeleitungen wieder zu den oberen
  Datenpins hochgeführt werden. `TinyCPUMain` ist wegen seiner Vernetzung
  derzeit eine Ausnahme; feste Bauteilanschlüsse, etwa an Multiplexern,
  erlauben kurze lokale Gegenrichtungen. Die Benutzeranordnung wird für
  diese Ausnahmen nicht automatisch neu gezeichnet.
- Möglichst wenige Konstanten verwenden. Jede braucht einen elektrischen
  Zweck. Gleiche feste Werte dürfen übersichtlich gemeinsam versorgt werden;
  offene Eingänge und lange Verteilungsschleifen sind keine Verbesserung.
- Diese Regeln gelten auch außerhalb der acht Funktionsboxen. Bestehende
  Nachweise für diese Boxen sind keine projektweite visuelle Abnahme.

So weit wie möglich gilt für sichtbare Leitungen:

- Zwischen zwei parallelen Leitungen bleibt eine Rasterzeile frei: bei
  Logisims 10-Pixel-Raster beträgt der Leitungsabstand mindestens 20 Pixel.
- Nach höchstens vier Leitungen bleiben drei Rasterzeilen frei: zwischen
  der letzten und der nächsten Spur liegen mindestens 40 Pixel.
- Bei unvollständigen Bündeln werden die tatsächlich vorhandenen Leitungen
  von oben beziehungsweise von links gezählt. Wo es übersichtlicher wird,
  sind zusammengehörige Signale als sichtbar verdrahtete Busse zu führen;
  ihre Bitbelegung muss dokumentiert bleiben.
- Benötigte Steuerbits dürfen über einen vollständigen Aufteiler oder nahe
  lokale Einzelbit-Abgriffe entnommen werden. Breite und Bitnummern des
  Steuerbusses bleiben unverändert und müssen bitgenau geprüft werden.
  Ein Vergleich des gesamten Steuerbusses mit einer Bitnummer ist keine
  Auswahl des betreffenden Signals.
- Funktionsboxen stehen so nah beieinander, wie ihre Anschlussauffächerung
  und die obigen Leitungsabstände erlauben. Große leere Umwege sind zu vermeiden.
- Innerhalb der oberen Pingruppen werden Blattpins möglichst auf die Höhe
  nahe gelegener Signalquellen beziehungsweise Zieleingänge gesetzt.
  Leitungen beginnen und enden am Pin waagrecht;
  erforderliche kurze Höhenversätze liegen möglichst nahe an der Logik.
- Splitter/Bus-Zusammenführungen müssen zu den angeschlossenen Signalen zeigen.
  Eine Spiegelung darf weder die Bitreihenfolge noch die Busbelegung verändern.

Seit dem Benutzerauftrag vom 9. November 2026 verwenden sämtliche FBoxen
ausschließlich Logisims eingebaute Darstellung `logisim_evolution`.
Eigene `appear`-Zeichnungen und nachgebildete Standardrechtecke sind nicht
zulässig. Die frühere Festlegung auf explizite Symbolansichten ist damit
ersetzt. Die Anschlussreihenfolge ergibt sich aus Logisims Standardgenerator
und den Blattpins; beim Verschieben von Blattpins sind deshalb sämtliche
betroffenen Instanzen nach Signalnamen neu zu verbinden und nativ zu prüfen.
Signalnamen, Breiten, Richtungen und Busbitbelegungen bleiben verbindlich.
Der Benutzer hat die Vierergruppen der äußeren Blattpins ausdrücklich bestätigt,
auch wenn die Auffächerung zu den dichteren Standardanschlüssen mehr Platz braucht.
Die folgenden Schutzregeln für die Decoderzeichnungen bleiben unverändert.

Die frühere Rasterüberarbeitung verwendete lange Spuren auf den Koordinaten
20/40/60/80 modulo 100 in beiden Achsen. Der Offline-Verifikator prüft
zusammenhängende gerade Läufe über 160 Pixel, auch über Leitungsabzweige
hinweg. Kurze Anschlussauffächerungen an unveränderlichen Bauteilpins,
insbesondere am Decoder und an Splittern, dürfen von diesem Raster abweichen.
Diese Ausnahme ist auf den Anschlussbereich begrenzt; sie rechtfertigt keine
engen Bündel über das gesamte Schaltblatt. Die geschützte interne Zeichnung
von `FetchDecodeControls` bleibt weiterhin unangetastet.

Am 7. November 2026 hat der Benutzer diese großflächige Umzeichnung
zurückgewiesen und die Angleichung an das vorherige Layout verlangt.
Die [wiederhergestellten Referenzzeichnungen](../../docs/tiny_cpu_layout_restoration_20261107.md)
bleiben daher erhalten. Die Gestaltungsziele rechtfertigen keine erneute
automatische Anordnung der bestehenden Blätter. Für exakt die im
`layout-restoration-v1.json` dokumentierten Geometrien gilt eine Ausnahme
von der Modulo-Rasterprüfung. Änderungen fallen wieder unter die Prüfung;
elektrische Netze, Schnittstellen und Tunnelverbot sind niemals ausgenommen.

Diese vom Benutzer am 31. Oktober 2026 ausdrücklich gewünschte
Modularisierung erlaubt das Umstrukturieren der Übersicht und das Extrahieren
fachlicher Teilkreise (AP 23). Sie ersetzt dafür die historischen Verbote
einer Neuanordnung der obersten Ebene. Öffentliche Kernpins, ISA, Taktbezug
und Verhalten bleiben erhalten; die vollständigen elektrischen Gates und
Negativkontrollen müssen anschließend wieder bestehen. Ein bloßer Wrapper
um die gesamte bisherige Übersicht erfüllt diese Regel nicht.

Die folgende Schutzregel für den handgezeichneten Decoder bleibt bestehen.

# Verbindliche Darstellungsregel für `FetchDecodeControls`

`FetchDecodeControls` ist eine bewusst von Hand gestaltete Schaltung. **Ihre
Darstellung darf nicht erneut umgezeichnet, automatisch angeordnet,
„aufgeräumt“ oder durch eine vermeintlich übersichtlichere Darstellung ersetzt
werden.** Das gilt für `TinyCPU.circ` und die eigenständige
Diagnoseschaltung unter `diagnostics/`.

Insbesondere dürfen Bauteile, Pins und Leitungswege nicht einzeln verschoben,
neu gruppiert oder durch Tunnel ersetzt werden. Eine andere Opcode-Gruppierung,
eine neue öffentliche Schnittstelle oder ein bestandener Test rechtfertigt
keine optische Neugestaltung.

Falls eine Größenänderung von `FetchDecodeControls` wirklich erforderlich ist,
ist ausschließlich eine **gleichmäßige proportionale Vergrößerung des gesamten
vorhandenen Bildes** zulässig: dieselbe Skalierung in x- und y-Richtung für
sämtliche Bauteile, Pins, Knickpunkte und Leitungsenden. Seitenverhältnis,
relative Positionen und Leitungsverläufe müssen dabei unverändert bleiben.
Eine bloße Vergrößerung der Zeichenfläche mit anschließender Neuplatzierung ist
nicht zulässig.

Vor jeder fachlich notwendigen Änderung innerhalb dieses Teilkreises muss ein
Test den konkreten elektrischen Fehler belegen. Danach ist die kleinste
mögliche Änderung an der bestehenden Zeichnung vorzunehmen. Wenn das nicht
ohne Umzeichnen möglich erscheint, ist die Änderung zu stoppen und zuerst mit
dem Schaltungsautor abzustimmen.

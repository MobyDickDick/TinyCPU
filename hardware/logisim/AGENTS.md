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

So weit wie möglich gilt für sichtbare Leitungen:

- Zwischen zwei parallelen Leitungen bleibt eine Rasterzeile frei: bei
  Logisims 10-Pixel-Raster beträgt der Leitungsabstand mindestens 20 Pixel.
- Nach höchstens vier Leitungen bleiben drei Rasterzeilen frei: zwischen
  der letzten und der nächsten Spur liegen mindestens 40 Pixel.
- Funktionsboxen stehen so nah beieinander, wie ihre Anschlussauffächerung
  und die obigen Leitungsabstände erlauben. Große leere Umwege sind zu vermeiden.
- Blattpins werden möglichst auf die Höhe ihrer Signalquellen beziehungsweise
  Zieleingänge gesetzt. Leitungen beginnen und enden am Pin waagrecht;
  erforderliche kurze Höhenversätze liegen möglichst nahe an der Logik.
- Splitter/Bus-Zusammenführungen müssen zu den angeschlossenen Signalen zeigen.
  Eine Spiegelung darf weder die Bitreihenfolge noch die Busbelegung verändern.

Die acht Funktionsboxen besitzen explizite, aus Logisim exportierte
Symbolansichten. Deren `circ-port`-Bindungen sichern die bisherige
Schnittstelle, während die Blattpins nach Signalhöhe angeordnet werden.
Beim Verschieben eines Pins muss seine Koordinatenreferenz im Symbol
mitgeführt werden. Die Symbolanschlüsse dürfen dabei nicht neu sortiert werden.

Die acht Funktionsboxen verwenden dafür lange Spuren auf den Koordinaten
20/40/60/80 modulo 100 in beiden Achsen. Der Offline-Verifikator prüft
zusammenhängende gerade Läufe über 160 Pixel, auch über Leitungsabzweige
hinweg. Kurze Anschlussauffächerungen an unveränderlichen Bauteilpins,
insbesondere am Decoder und an Splittern, dürfen von diesem Raster abweichen.
Diese Ausnahme ist auf den Anschlussbereich begrenzt; sie rechtfertigt keine
engen Bündel über das gesamte Schaltblatt. Die geschützte interne Zeichnung
von `FetchDecodeControls` bleibt weiterhin unangetastet.

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

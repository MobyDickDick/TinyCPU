# Verbindliche Struktur der CPU-Übersicht

`TinyCPUMain` ist ausschließlich eine Übersicht aus fachlich benannten
Funktionsboxen, öffentlichen Anschlusspins und deren Leitungen. Einzelne
Gatter, Multiplexer, Splitter, Konstanten, Register, RAMs, Tunnel und Probes
gehören in die zuständigen Teilkreise. Neue Fehlerkorrekturen dürfen diese
Abstraktionsgrenze nicht wieder auflösen. Diagnoseanzeigen gehören in eine
eigene Diagnosebox. Steuersignale dürfen als benannter, dokumentierter Bus
zwischen Funktionsboxen geführt und ausschließlich darin aufgeteilt werden.

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

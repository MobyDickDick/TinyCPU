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

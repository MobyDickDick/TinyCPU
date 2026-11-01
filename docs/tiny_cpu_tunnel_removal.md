# Tunnelentfernung vom 1. November 2026

Alle 738 Tunnel des eingehenden Arbeitsstands wurden durch sichtbare,
rechtwinklige Leitungen ersetzt: 731 innerhalb der acht Funktionsboxen in
`TinyCPU.circ`, sieben in `diagnostics/TinyCPU-ErrorFlags.circ`.
Die abschließende XML-Prüfung aller 24 Projektdateien mit insgesamt
56 Schaltkreisen findet **null Tunnel-Komponenten**.

Die Bauteilpositionen und öffentlichen Schnittstellen wurden beibehalten.
Innerhalb des Kerns sind ausschließlich die acht Funktionsboxen verändert;
insbesondere bleiben die eingehenden Benutzeränderungen an
`FetchDecodeControls` und den übrigen Teilkreisen erhalten.
Der positionsunabhängige elektrische Topologie-Fingerabdruck ist vor und
nach dem Umbau identisch und entspricht weiterhin dem Steuerbusvertrag:

`0d7893c6fbc0869006a4bd8ffa96313c405fac87719787ca1e71a3348159f980`

Auch die separate ErrorFlags-Diagnose behält ihre ursprüngliche Netzaufteilung.
Die neuen Leitungen der acht Funktionsboxen besitzen keine impliziten
T-Kontakte oder kollinearen Überlappungen. Logisims eigene Zeichenfunktion
wurde für die Sichtprüfung verwendet; die PNGs liegen unter
`artifacts/no-tunnels/`.

## Dauerhafte Prüfungen

Sowohl `python src/tiny_cpu_verify.py` als auch
`python scripts/check-logisim-circuit.py` verwerfen Tunnel in jedem
Schaltblatt, einschließlich unbenutzter Teilkreise und Diagnosedateien.
Der statische Prüfer verfolgt reale Signalquellen durch die Bitzuordnung
von Splittern. Ein unterbrochener Steuerbus wird dadurch nicht als Quelle
anerkannt. Regressionstests prüfen diese Unterbrechung und das Tunnelverbot.
Die verbindliche Projektregel steht in `hardware/logisim/AGENTS.md`.

## Abnahme

- Offline-Verifikator und statischer Schaltungsprüfer: bestanden.
- Logisim: 61 Kernfixtures, sieben Systemfixtures sowie die Kern-Traces
  einschließlich Countdown: bestanden.
- Ergänzende elektrische Prüfungen für Kernmutation, PRINT, unmittelbare
  Operanden, Adressregister und Operator-Panel: bestanden.
- Separate ErrorFlags-Diagnose: elektrische Ausgänge definiert, keine E/U-Werte.
- Python-Suite: 215 von 216 Tests bestanden. Der eine Fehler bestand bereits
  vor dem Umbau: `test_decoder_mutations_find_neutral_inputs_without_constant_labels`
  erwartet entfernte Konstanten an `ACC_LOAD_REQUEST`.
- Die STORE- und Decoder-Skripte scheitern ebenfalls beim Aufbau ihrer
  Negativkontrollen an diesen alten Konstantenannahmen. Ihre positiven
  Simulatorfälle bestehen. Die geschützte Decoderzeichnung wurde dafür
  nicht verändert.

Die vollständigen Prüfprotokolle, der gesicherte eingehende Arbeitsstand
und die Vergleichsnachweise liegen unter `artifacts/no-tunnels/`.

Die anschließend gewünschte kompaktere Anordnung und die Abstände zwischen
Leitungen sind in der [Lesbarkeitsüberarbeitung](tiny_cpu_readable_wiring.md)
dokumentiert. Sie ersetzt die hier beschriebene anfängliche Anordnung.

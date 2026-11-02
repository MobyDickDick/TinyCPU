# TinyCPU-FetchDecodeControls: Grundidee

Begleitbeschreibung zu [TinyCPU-FetchDecodeControls.circ](TinyCPU-FetchDecodeControls.circ).

Diese Datei beschreibt die separat ladbare Diagnosefassung. Sie kann sich
in Schnittstelle und Entwicklungsstand vom eingebetteten Kernblatt unterscheiden.

## FetchDecodeControls

Übersetzt den sechs Bit breiten Opcode in die einzelnen Befehls-, Auswahl- und
Schreibsteuersignale. Die handgezeichnete Decoderstruktur bestimmt, welche Verarbeitung
für den aktuellen Befehl aktiv ist.

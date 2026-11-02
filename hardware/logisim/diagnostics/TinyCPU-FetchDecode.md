# TinyCPU-FetchDecode: Grundidee

Begleitbeschreibung zu [TinyCPU-FetchDecode.circ](TinyCPU-FetchDecode.circ).

Diese Datei beschreibt die separat ladbare Diagnosefassung. Sie kann sich
in Schnittstelle und Entwicklungsstand vom eingebetteten Kernblatt unterscheiden.

## FetchDecode

Speichert den Programmzähler und liest damit das 22-Bit-Befehlswort aus dem ROM. Wählt
zwischen dem nächsten Befehl, einem Sprung und einem Interruptziel und erkennt das Ende
des zulässigen Programmbereichs.

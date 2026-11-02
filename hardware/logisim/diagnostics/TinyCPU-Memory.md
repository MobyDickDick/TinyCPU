# TinyCPU-Memory: Grundidee

Begleitbeschreibung zu [TinyCPU-Memory.circ](TinyCPU-Memory.circ).

Diese Datei beschreibt die separat ladbare Diagnosefassung. Sie kann sich
in Schnittstelle und Entwicklungsstand vom eingebetteten Kernblatt unterscheiden.

## Memory

Speichert zu jeder Datenzelle sowohl einen 16-Bit-Wert als auch ein Gültigkeitsbit in
zwei parallelen RAMs. Schreibfreigabe und Takt übernehmen beide gemeinsam; beim Lesen
erscheinen Wert und Gültigkeit zusammen.

# TinyCPU-ErrorFlags: Grundidee

Begleitbeschreibung zu [TinyCPU-ErrorFlags.circ](TinyCPU-ErrorFlags.circ).

Diese Datei beschreibt die separat ladbare Diagnosefassung. Sie kann sich
in Schnittstelle und Entwicklungsstand vom eingebetteten Kernblatt unterscheiden.

## ErrorFlags

Speichert die sechs Fehlerflags OVF, DIV0, ADDR, INV, ILL und INPUT. Ein gesetzter
Fehler bleibt über weitere Befehle erhalten; CLEAR_ERROR löscht die gespeicherten Fehler
beim entsprechenden Taktschritt.

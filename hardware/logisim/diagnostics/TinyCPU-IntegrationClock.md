# TinyCPU-IntegrationClock: Grundidee

Begleitbeschreibung zu [TinyCPU-IntegrationClock.circ](TinyCPU-IntegrationClock.circ).

Diese Datei beschreibt die separat ladbare Diagnosefassung. Sie kann sich
in Schnittstelle und Entwicklungsstand vom eingebetteten Kernblatt unterscheiden.

## IntegrationClock

Verteilt den eingehenden Takt auf Datenpfad, Adresspfad, Speicher, Fehlerflags und
Befehlssteuerung. Erzeugt selbst keinen neuen Takt und verändert dessen Frequenz nicht.

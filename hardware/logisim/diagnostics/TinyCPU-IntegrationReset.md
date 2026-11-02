# TinyCPU-IntegrationReset: Grundidee

Begleitbeschreibung zu [TinyCPU-IntegrationReset.circ](TinyCPU-IntegrationReset.circ).

Diese Datei beschreibt die separat ladbare Diagnosefassung. Sie kann sich
in Schnittstelle und Entwicklungsstand vom eingebetteten Kernblatt unterscheiden.

## IntegrationReset

Leitet RESET an den Reset-Eingang der Befehlssteuerung weiter. Setzt damit den
Befehlsablauf zurück; Daten-RAM, Akkumulator und Fehlerflags erhalten darüber keinen
allgemeinen Löschimpuls.

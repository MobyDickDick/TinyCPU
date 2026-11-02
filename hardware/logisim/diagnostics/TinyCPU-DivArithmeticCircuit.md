# TinyCPU-DivArithmeticCircuit: Grundidee

Begleitbeschreibung zu [TinyCPU-DivArithmeticCircuit.circ](TinyCPU-DivArithmeticCircuit.circ).

Diese Datei beschreibt die separat ladbare Diagnosefassung. Sie kann sich
in Schnittstelle und Entwicklungsstand vom eingebetteten Kernblatt unterscheiden.

## DivArithmeticCircuit

Dividiert den linken Operanden durch den rechten. Die Ergebnisfreigabe berücksichtigt
die Gültigkeit der Eingänge; eine aktivierte Division durch null wird gesondert
gemeldet.

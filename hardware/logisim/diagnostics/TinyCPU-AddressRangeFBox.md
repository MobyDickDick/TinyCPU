# TinyCPU-AddressRangeFBox: Grundidee

Begleitbeschreibung zu [TinyCPU-AddressRangeFBox.circ](TinyCPU-AddressRangeFBox.circ).

Diese Datei beschreibt die separat ladbare Diagnosefassung. Sie kann sich
in Schnittstelle und Entwicklungsstand vom eingebetteten Kernblatt unterscheiden.

## AddressRangeFBox

Entscheidet, ob eine erkannte Bereichsüberschreitung für den aktuellen Speicherbefehl
relevant ist. Verknüpft dazu die verwendete Adressierungsart mit Bereichs- und
Offsetfehlern.

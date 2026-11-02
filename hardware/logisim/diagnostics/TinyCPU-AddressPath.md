# TinyCPU-AddressPath: Grundidee

Begleitbeschreibung zu [TinyCPU-AddressPath.circ](TinyCPU-AddressPath.circ).

Diese Datei beschreibt die separat ladbare Diagnosefassung. Sie kann sich
in Schnittstelle und Entwicklungsstand vom eingebetteten Kernblatt unterscheiden.

## AddressPath

Speichert die Basisadresse und ihre Gültigkeit im Adressregister. Ein Addierer bildet
zusätzlich Basis plus Offset und liefert den Übertrag für die nachfolgende
Bereichsprüfung.

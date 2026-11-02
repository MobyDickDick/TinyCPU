# TinyCPU-Datapath: Grundidee

Begleitbeschreibung zu [TinyCPU-Datapath.circ](TinyCPU-Datapath.circ).

Diese Datei beschreibt die separat ladbare Diagnosefassung. Sie kann sich
in Schnittstelle und Entwicklungsstand vom eingebetteten Kernblatt unterscheiden.

## Datapath

Speichert den 16-Bit-Akkumulatorwert und sein Gültigkeitsbit bei aktivem ACC_LOAD an der
Taktflanke. Ein Vergleich mit null liefert ZERO und NEGATIVE; DATAPATH_STARTUP_RESET
löscht bei 1 beide Register und liegt im CPU-Kern in der AccumulatorUnit dauerhaft auf
0, also inaktiv.

Im CPU-Kern wird der vorhandene Löscheingang durch die feste Null
nicht betätigt. Sie definiert den Ruhepegel dieses Steuereingangs und
kann nicht einfach entfallen. RESET der CPU setzt nach dem
bestehenden Vertrag den Befehlsablauf zurück, ohne diese Register zu löschen.

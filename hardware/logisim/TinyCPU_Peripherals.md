# TinyCPU_Peripherals: Grundidee

Begleitbeschreibung zu [TinyCPU_Peripherals.circ](TinyCPU_Peripherals.circ).

## TinyCPUSystemMain

Verbindet den CPU-Kern mit einem speicheradressierten Ausgabeport und einer
Interruptsteuerung. Führt gemeinsamen Takt und Reset sowie die sichtbaren Ausgabe- und
Interruptzustände zusammen.

## CPUIntegrationBoundary

Passt die öffentlichen Kernanschlüsse an den externen Speicher- und Interruptpfad an.
Reicht gelesene Werte, Schreibanforderungen, Befehlsgrenzen und Interruptbefehle
zwischen CPU und Umgebung weiter.

## OutputPort

Speichert einen freigegebenen Ausgabewert und sein Gültigkeitsbit in zwei Registern. Der
Wert bleibt bis zum nächsten akzeptierten Schreiben erhalten; RESET löscht den
Ausgabestand.

## OutputMemoryPath

Unterscheidet normale RAM-Adressen von der reservierten Ausgabeadresse. Leitet
Schreibzugriffe an RAM oder Ausgaberegister und wählt beim Lesen zwischen RAM-Wert und
gespeichertem Ausgabewert, jeweils samt Gültigkeit.

## InterruptController

Merkt eine steigende Interruptanforderung, bis sie an einer Befehlsgrenze angenommen
werden darf. Verwaltet Freigabe, Rückkehradresse und Handlerzustand sowie eine gültige
oder unzulässige Rückkehr.

# TinyCPU-Dokumentation

Dieses Verzeichnis enthält ausschließlich Dokumentation zur TinyCPU:

- [`tiny_cpu.md`](tiny_cpu.md): Architektur, Befehlssatz und Simulator
- [`tiny_cpu_alu_sketch.md`](tiny_cpu_alu_sketch.md): Entwurf der ALU
- [`tiny_cpu_top_level_template.md`](tiny_cpu_top_level_template.md): Referenz für die Top-Level-Integration
- [`tiny_cpu_test_guide.md`](tiny_cpu_test_guide.md): Testanleitung für die Logisim-Schaltung
- [`logisim_diagnostics_known_issues.md`](logisim_diagnostics_known_issues.md): bekannte Besonderheiten der Diagnoseschaltungen
- [`tiny_cpu_roadmap.md`](tiny_cpu_roadmap.md): Hardware-Arbeitsplan
- [`tiny_cpu_debugger_plan.md`](tiny_cpu_debugger_plan.md): abgegrenzter Vorschlag für AP 16 (symbolisches Debugging)
- [`tiny_cpu_debugger.md`](tiny_cpu_debugger.md): Bedienung und JSON-Vertrag des symbolischen Debuggers
- [`tiny_cpu_compatibility.md`](tiny_cpu_compatibility.md): Kompatibilitätsregeln
- [`tiny_cpu_1_0_release_plan.md`](tiny_cpu_1_0_release_plan.md): Releaseplan für TinyCPU 1.0
- [`tiny_cpu_1_0_release_notes.md`](tiny_cpu_1_0_release_notes.md): Release Notes für TinyCPU 1.0

Die Dokumentation der Logisim-Implementierung befindet sich ergänzend unter
[`hardware/logisim/README.md`](../hardware/logisim/README.md).

## Planungsstand

Die dokumentierten Arbeitspakete AP 1 bis AP 16 sind abgeschlossen. Insbesondere
ist AP 16 nicht nur ein Vorschlag: Implementierung, Bedienungsanleitung und
automatisierte Abnahme des symbolischen Debuggers liegen im Repository. Derzeit
gibt es deshalb **kein weiteres dokumentiertes Arbeitspaket**, das unmittelbar
abgearbeitet werden könnte. Vor AP 17 ist zuerst eine neue, abgegrenzte
Produktentscheidung mit Kompatibilitätsfolgen und messbaren Abnahmekriterien zu
dokumentieren; die noch nicht ausgewählten Kandidaten stehen im
[`tiny_cpu_roadmap.md`](tiny_cpu_roadmap.md#funktionsstatus-und-weitere-planung).

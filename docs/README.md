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
- [`tiny_cpu_profiles_plan.md`](tiny_cpu_profiles_plan.md): abgegrenzter Vorschlag für AP 17 (zweites Hardwareprofil)
- [`tiny_cpu_compatibility.md`](tiny_cpu_compatibility.md): Kompatibilitätsregeln
- [`tiny_cpu_1_0_release_plan.md`](tiny_cpu_1_0_release_plan.md): Releaseplan für TinyCPU 1.0
- [`tiny_cpu_1_0_release_notes.md`](tiny_cpu_1_0_release_notes.md): Release Notes für TinyCPU 1.0

Die Dokumentation der Logisim-Implementierung befindet sich ergänzend unter
[`hardware/logisim/README.md`](../hardware/logisim/README.md).

## Planungsstand

Die Arbeitspakete AP 1 bis AP 16 sind abgeschlossen. AP 17 für ein zusätzliches
8/8-Hardwareprofil befindet sich in Umsetzung; Profil, Softwarewerkzeuge,
Schaltung und der profilbezogene elektrische Matrixvertrag sind vorhanden. Der
profilbezogene Kernlauf ist automatisiert; elektrische Matrix und gemeinsame
Endabnahme stehen noch aus. Umfang, Kompatibilitätsfolgen,
Abnahme und Reihenfolge stehen im
[`tiny_cpu_profiles_plan.md`](tiny_cpu_profiles_plan.md); Peripherie und
Integration bleiben Kandidaten für einen späteren eigenen Vorschlag.

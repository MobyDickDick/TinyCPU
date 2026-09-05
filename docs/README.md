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
- [`tiny_cpu_peripherals_plan.md`](tiny_cpu_peripherals_plan.md): abgegrenzter Vorschlag für AP 18 (Peripherie und Integration)
- [`tiny_cpu_compatibility.md`](tiny_cpu_compatibility.md): Kompatibilitätsregeln
- [`tiny_cpu_1_0_release_plan.md`](tiny_cpu_1_0_release_plan.md): Releaseplan für TinyCPU 1.0
- [`tiny_cpu_1_0_release_notes.md`](tiny_cpu_1_0_release_notes.md): Release Notes für TinyCPU 1.0

Die Dokumentation der Logisim-Implementierung befindet sich ergänzend unter
[`hardware/logisim/README.md`](../hardware/logisim/README.md).

## Enthaltene Logisim-Unterstützung

Logisim-evolution ist als festgelegte Projektabhängigkeit vollständig in den
TinyCPU-Prüfablauf integriert: Das Repository enthält die beiden ausführbaren
Schaltungsprojekte, Profile, ROM-Fixtures, elektrischen Testmatrizen, Launcher
und CI-Konfiguration. Die unterstützte Simulatorversion 4.1.0 ist fest
vorgegeben und wird vom Launcher automatisch aus `vendor/`, dem lokalen Cache
oder – als letzte Möglichkeit – von der versionierten Upstream-Adresse
bezogen. Das große Upstream-JAR selbst wird derzeit nicht als Git-Blob
dupliziert. „Logisim ist im Projekt enthalten“ bezeichnet daher die
reproduzierbare Integration und automatische Bereitstellung, nicht eine
Quellkopie des externen Simulators.

## Planungsstand

Die Arbeitspakete AP 1 bis AP 17 sind abgeschlossen. AP 17 ergänzt ein
8/8-Hardwareprofil samt Profilvertrag, Softwarewerkzeugen, eigener Schaltung,
Kernlauf und vollständiger elektrischer ISA-/Fehlermatrix. Die gemeinsame
Endabnahme beider Profile läuft verpflichtend bei jeder CI-Prüfung. Umfang,
Kompatibilitätsfolgen, Abnahme und Reihenfolge stehen im
[`tiny_cpu_profiles_plan.md`](tiny_cpu_profiles_plan.md). Als nächster
optionaler Entwicklungsschritt ist AP 18 für einen Ausgabeport und eine
maskierbare Interruptquelle abgegrenzt. Dessen versionierte System-,
Maschinenformat- und Trace-Verträge sowie das Softwaremodell sind
abgeschlossen. Die elektrische Implementierung ist mit einem vertraglich
geprüften Ausgabeport-Baustein begonnen; Speicherpfadanbindung,
Interruptsteuerung und elektrische Systemabnahme sind noch offen.

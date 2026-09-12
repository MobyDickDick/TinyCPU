# TinyCPU-Dokumentation

Dieses Verzeichnis enthält ausschließlich Dokumentation zur TinyCPU:

- [`tiny_cpu.md`](tiny_cpu.md): Architektur, Befehlssatz und Simulator
- [`tiny_cpu_alu_sketch.md`](tiny_cpu_alu_sketch.md): Entwurf der ALU
- [`tiny_cpu_top_level_template.md`](tiny_cpu_top_level_template.md): Referenz für die Top-Level-Integration
- [`tiny_cpu_test_guide.md`](tiny_cpu_test_guide.md): Testanleitung für die Logisim-Schaltung
- [`tiny_cpu_instruction_status.md`](tiny_cpu_instruction_status.md): aktuell nachgewiesener Funktionsstand aller Befehle
- [`logisim_diagnostics_known_issues.md`](logisim_diagnostics_known_issues.md): bekannte Besonderheiten der Diagnoseschaltungen
- [`tiny_cpu_roadmap.md`](tiny_cpu_roadmap.md): Hardware-Arbeitsplan
- [`tiny_cpu_debugger_plan.md`](tiny_cpu_debugger_plan.md): abgegrenzter Vorschlag für AP 16 (symbolisches Debugging)
- [`tiny_cpu_debugger.md`](tiny_cpu_debugger.md): Bedienung und JSON-Vertrag des symbolischen Debuggers
- [`tiny_cpu_profiles_plan.md`](tiny_cpu_profiles_plan.md): abgegrenzter Vorschlag für AP 17 (zweites Hardwareprofil)
- [`tiny_cpu_peripherals_plan.md`](tiny_cpu_peripherals_plan.md): abgegrenzter Vorschlag für AP 18 (Peripherie und Integration)
- [`tiny_cpu_circuit_debug_plan.md`](tiny_cpu_circuit_debug_plan.md): zehnstufiger Arbeitsplan für die reproduzierbare Fehlersuche in `TinyCPU.circ`
- [`tiny_cpu_recovery_work_packages.md`](tiny_cpu_recovery_work_packages.md): priorisierte Arbeitspakete zur Wiederherstellung der elektrischen 16/12-CPU
- [`tiny_cpu_compatibility.md`](tiny_cpu_compatibility.md): Kompatibilitätsregeln
- [`tiny_cpu_1_0_release_plan.md`](tiny_cpu_1_0_release_plan.md): Releaseplan für TinyCPU 1.0
- [`tiny_cpu_1_0_release_notes.md`](tiny_cpu_1_0_release_notes.md): Release Notes für TinyCPU 1.0

Die Dokumentation der Logisim-Implementierung befindet sich ergänzend unter
[`hardware/logisim/README.md`](../hardware/logisim/README.md).

## Enthaltene Logisim-Unterstützung

Logisim-evolution ist als festgelegte Projektabhängigkeit vollständig in den
TinyCPU-Prüfablauf integriert: Das Repository enthält das ausführbare
16/12-Schaltungsprojekt, Profil, ROM-Fixtures, elektrische Testmatrix, Launcher
und CI-Konfiguration. Die unterstützte Simulatorversion 4.1.0 ist fest
vorgegeben und wird vom Launcher automatisch aus `vendor/`, dem lokalen Cache
oder – als letzte Möglichkeit – von der versionierten Upstream-Adresse
bezogen. Das große Upstream-JAR selbst wird derzeit nicht als Git-Blob
dupliziert. „Logisim ist im Projekt enthalten“ bezeichnet daher die
reproduzierbare Integration und automatische Bereitstellung, nicht eine
Quellkopie des externen Simulators.

## Planungsstand

Die Arbeitspakete AP 1 bis AP 16 sind abgeschlossen. Das in AP 17 ergänzte
8/8-Experiment wurde stillgelegt und vollständig aus der ausführbaren
Unterstützung entfernt: Sechs Opcode-Bits des weiter unterstützten
16/12-Profils reichen für die vorgesehene Befehlsmenge aus. Der historische
Plan enthält den Stilllegungsvermerk. Als nächster
optionaler Entwicklungsschritt ist AP 18 für einen Ausgabeport und eine
maskierbare Interruptquelle abgegrenzt. Dessen versionierte System-,
Maschinenformat- und Trace-Verträge sowie das Softwaremodell sind
abgeschlossen. Die elektrische Implementierung ist mit einem vertraglich
geprüften Ausgabeport-Baustein begonnen, dessen atomare Daten- und
Steuerverdrahtung vollständig offline geprüft wird. Speicherpfad- und
Interruptsteuerungsgrenze sind ebenfalls vertraglich festgelegt. Die
Interruptanforderung besitzt nun einen direkt verdrahteten, taktsynchron
zurücksetzbaren Pegelspeicher und eine geprüfte Erkennung ausschließlich
ansteigender Flanken. Der Impuls setzt ein taktsynchrones Pending-Register;
dessen Rückkopplung hält maskierte Anforderungen, während Reset den Zustand
löscht. Pending-Zustand, Interruptmaske, Instruktionsgrenze und invertierter
Handlerzustand sind nun zum Annahmeimpuls verknüpft; derselbe Impuls löscht das
Pending-Bit gezielt. Die funktionale Einfügung
dieser Grenzen in die vollständige CPU und die elektrische Systemabnahme sind
noch offen. Die Speicherpfadgrenze des Ausgabeports ist inzwischen vollständig
verdrahtet und wird offline einschließlich ihrer getrennten RAM-/Port-Freigaben
und gemeinsamen Wert-/Validitätsauswahl geprüft.

Unabhängig von dieser Funktionserweiterung grenzt
[`tiny_cpu_circuit_debug_plan.md`](tiny_cpu_circuit_debug_plan.md) AP 19 als
zehn einzeln abnehmbare Aufgaben ab. Das Paket dient der reproduzierbaren
Fehlersuche an der aktuellen `TinyCPU.circ`, ohne einen manuellen Redraw durch
eine historische Zeichnung zu ersetzen oder die abgeschlossenen ISA-Verträge
neu zu öffnen.

Die inzwischen erneut fehlgeschlagenen Offline- und elektrischen Profilgates
werden in
[`tiny_cpu_recovery_work_packages.md`](tiny_cpu_recovery_work_packages.md) als
AP 20 behandelt. Nach der Stilllegung des 8/8-Experiments ist 20.4 für Reset, Takt und Fetch der 16/12-Schaltung das nächste aktive Paket.

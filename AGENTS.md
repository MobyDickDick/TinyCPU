# Schaltplan-Lesbarkeit

Für sämtliche bestehenden und neuen Elektroschemas dieses Projekts gilt der
Benutzerstil in [`docs/tiny_cpu_schematic_style.md`](docs/tiny_cpu_schematic_style.md),
einschließlich Pinanordnung, Vierergruppen, freien Leitungsspuren und möglichst
wenigen Konstanten. Diese Vorgaben sind bei jeder Schaltplanänderung anzuwenden.
Eine elektrisch bestandene Prüfung belegt noch keine gute Lesbarkeit.

Für Logisim gelten zusätzlich die Regeln in
[`hardware/logisim/AGENTS.md`](hardware/logisim/AGENTS.md), insbesondere der
Schutz des handgezeichneten `FetchDecodeControls`, das Tunnelverbot und die
Schnittstellenverträge. Die allgemeine Layoutvorgabe hebt diesen Schutz nicht auf.

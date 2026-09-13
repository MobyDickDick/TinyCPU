# Stillgelegtes AP 17: zusätzliches 8/8-Profil

Das experimentelle Hardwareprofil `tinycpu-8-8` wurde wieder entfernt. Es war
für die TinyCPU-ISA nicht erforderlich: Die unveränderten sechs Opcode-Bits des
16/12-Profils stellen bereits 64 Codes bereit und decken damit die vorgesehene
Befehlsmenge ab.

Die Schaltung, ihr Maschinenformat, ihre ROM-/Trace-Fixtures, ihre elektrische
Matrix und die ausschließlich zu ihrer Diagnose vorhandenen Probe-Skripte sind
nicht mehr Bestandteil des Repositorys. Das einzige unterstützte CPU-Profil ist
`tinycpu-16-12` mit 16 Daten- und 12 Adressbits. Profilbewusste Werkzeuge
behalten ihre Schnittstelle, weisen den stillgelegten Profilnamen aber als
unbekannt zurück.

AP 20 wird deshalb nur mit der 16/12-Schaltung fortgesetzt. Historische
Diagnoseeinträge zu 8/8 bleiben im Diagnosebericht als Protokoll früherer Läufe
erkennbar; sie beschreiben keine aktuelle Abnahme und kein ausstehendes Paket.

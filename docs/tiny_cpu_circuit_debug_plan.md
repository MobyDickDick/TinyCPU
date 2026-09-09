# AP 19: `TinyCPU.circ` systematisch debuggen und stabilisieren

## Anlass und Ziel

Die vorhandenen automatisierten Prüfungen sollen den eingecheckten Stand
qualifizieren, ersetzen aber keine reproduzierbare Untersuchung eines konkret beobachteten
Fehlers in der manuell gepflegten Logisim-Zeichnung. AP 19 öffnet deshalb weder
die ISA noch die abgeschlossenen Produktverträge erneut. Das Paket führt in
**zehn einzeln abnehmbaren Arbeitsaufgaben** von einer Fehlerbeschreibung zu
einer im unterstützten Logisim-evolution 4.1.0 nachweisbar funktionierenden
Variante von `hardware/logisim/TinyCPU.circ`.

„Funktionierend“ bedeutet in diesem Paket:

- das unveränderte 16/12-Profil lädt ohne Diagnosefehler und lässt sich
  definiert zurücksetzen und takten;
- der Countdown sowie alle 50 Opcode-Fälle und sechs Sticky-Fehlerfälle stimmen
  elektrisch mit der Python-VM überein;
- ein dokumentierter manueller Kurztest zeigt Fetch, Ausführung, Ausgabe,
  Normalhalt und Fehlerhalt nachvollziehbar in der GUI;
- ein frischer Checkout reproduziert das Ergebnis, ohne eine historische
  Zeichnung oder erzeugte Diagnosedatei als neue Schaltungsquelle zu benutzen.

Der aktuelle `HEAD` zu Beginn der Bearbeitung ist festzuhalten. Die
eingecheckte `TinyCPU.circ` dieses Commits ist die einzige Ausgangsbasis. Ein
Redraw darf nicht durch eine ältere vermeintlich funktionierende Datei ersetzt
werden; repariert werden nur am aktuellen Stand nachgewiesene Netze und
Bauteilattribute.

## Die zehn Arbeitsaufgaben

| Aufgabe | Arbeit | Ergebnis | Abnahme |
|---|---|---|---|
| **19.1 Fehlerbild und Baseline einfrieren** | Logisim-/Java-Version, Commit, Startblatt, Bedienfolge, Eingaben, erwartetes und tatsächliches Ergebnis sowie das erste fehlerhafte Taktereignis protokollieren. Vor Änderungen Offline- und elektrische Tests ausführen und Rohartefakte sichern. | Eine kurze, wiederholbare Reproduktion statt einer allgemeinen Aussage wie „CPU funktioniert nicht“. | Eine zweite Person kann den Fehler am festgehaltenen Commit reproduzieren; nicht reproduzierbare Beobachtungen werden ausdrücklich als offen markiert und nicht durch Vermutung „repariert“. |
| **19.2 Projektladung und Hierarchie isolieren** | Zuerst die drei `smoke/`-Projekte, dann die erzeugten Diagnoseblätter und zuletzt `TinyCPU.circ` laden. Rekursion, fehlende Unterblätter, diagonale beziehungsweise Null-Längen-Leitungen und auffälligen Ressourcenverbrauch prüfen. | Das Problem ist entweder der Umgebung, einem einzelnen Blatt oder der Integration `TinyCPUMain` zugeordnet. | Alle ladbaren Stufen und die erste scheiternde Stufe stehen mit Startdauer, Ergebnis und Logisim-Protokoll in einem Diagnosebericht. |
| **19.3 Takt, Reset, PC und Fetch prüfen** | Einen Reset und die ersten Fetch-Flanken verfolgen. `CLK`, `RESET`, `PC_OUT`, ROM-Wort, `PROGRAM_LIMIT`, PC-Fortschaltung und Bereichsfehler gegen den erwarteten Kerntrace prüfen. | Ein minimales Fetch-Programm erreicht deterministisch Instruktion 0, 1 und `HALT`, oder der erste abweichende benannte Port ist bekannt. | Ein elektrischer Trace des Minimalprogramms stimmt flankenweise mit der VM überein; Reset liefert bei zwei Läufen denselben Anfangszustand. |
| **19.4 Decoder-Steuerfläche vollständig abgleichen** | Für jedes Maschinenwort Opcode- und Argumentdekodierung getrennt untersuchen. Gegenseitigen Ausschluss der Operationssignale, genau eine passende Argumentquelle und die Direktsteuerungen für Sprünge, E/A, Fehlerlöschen und Halt prüfen. | Keine vertauschten Pinreihenfolgen, zusammengeführten Steuernetze oder schwebenden Decoder-Ausgänge. | Eine automatisch erzeugte Decode-Tabelle deckt alle 50 Opcodes ab und vergleicht jeden benannten Ausgang mit der Opcode-Tabelle; Negativfälle prüfen unbekannte Opcodes. |
| **19.5 Akkumulator und Rechenpfad debuggen** | Vom gewählten Operanden über `Operations`, Ergebnis-/Validitätswahl und Write-Enable bis zum Akkumulator verfolgen. Lade-, `NOT`-, arithmetische und bitweise Fälle sowie Overflow und ungültige Operanden isolieren. | Wert und Validitätsbit werden an derselben vorgesehenen Flanke geschrieben; inaktive Zweige überschreiben den Akkumulator nicht. | Kleine ROMs prüfen mindestens jede Operationsfamilie, Null, Vorzeichengrenzen, Überlauf und Invalidität elektrisch gegen die VM. |
| **19.6 Adresspfad und Speicher debuggen** | Direktadresse, Adressregister und Register-plus-Offset bis zur effektiven Adresse verfolgen. Daten- und Valid-RAM, gemeinsame Adresse, Read/Write-Enable, Adressgrenze und `STORE` ohne unbeabsichtigtes Akkumulatorladen prüfen. | Alle vier Adressierungsarten lesen und schreiben die richtige Zelle; Wert und Validität bleiben gekoppelt. | Schreib-/Leseprogramme für jede Adressierungsart sowie Grenzadressen bestehen; eine ungültige oder überlaufende Adresse setzt ausschließlich die vorgesehenen Folgen. |
| **19.7 Sprünge, Ausgabe, Halt und Fehlerflags prüfen** | Bedingte Sprünge jeweils genommen und nicht genommen testen. `PRINT`, `PRINT_ADDRESS`, `HALT`, `HALT_ERROR`, alle sechs set-dominanten Sticky-Flags und `CLEAR_ERROR` bis zu den Top-Level-Pins verfolgen. | Kontrollfluss und beobachtbare Endpunkte sind nicht mit Daten- oder fremden Fehlernetzen kurzgeschlossen. | Separate Fixtures decken beide Sprungpfade, gültige/ungültige Ausgabe, Normal-/Fehlerhalt, jedes Fehlerbit und Set-vor-Clear-Priorität ab. |
| **19.8 Ersten abweichenden Netzübergang minimal reparieren** | Für jeden reproduzierten Fehler die VM-/Logisim-Traces am ersten Unterschied teilen und genau den Übergang Quelle-Port → Netz → Ziel-Port korrigieren. Nach jeder Korrektur den fokussierten Test und anschließend die Offline-Suite ausführen. | Kleine, reviewbare Änderungen mit einer belegten Ursache; keine großflächige Neuverdrahtung auf Verdacht. | Jede Änderung besitzt einen vor der Änderung fehlschlagenden Regressionstest, der danach besteht. Tests verwenden Namen und Topologie, niemals historische Canvas-Koordinaten. |
| **19.9 Vollständige elektrische Regression und GUI-Kurztest** | Countdown und komplette 16/12-ISA-/Fehlermatrix mit dem gepinnten Simulator ausführen. Danach den dokumentierten GUI-Ablauf mit Reset, Takten, Ausgabe und beiden Haltarten durchführen. | Automatisierte Architekturparität und praktische Bedienbarkeit sind getrennt belegt. | `scripts/test-offline.sh` und `scripts/test-logisim.sh` bestehen aus einem sauberen Arbeitsbaum; Roh- und Normaltraces bleiben erhalten. Der GUI-Kurztest ist mit erwarteten Beobachtungen dokumentiert. |
| **19.10 Funktionsfähigen Kandidaten einfrieren** | Geänderte Schaltung, ausschließlich aus ihr erzeugte Diagnoseblätter, Tests und Fehlerbericht gemeinsam reviewen. In einem zweiten frischen Checkout die Abnahme wiederholen und den exakten Commit als Kandidaten kennzeichnen. | Eine reproduzierbare, rückverfolgbare Variante statt einer nur lokal funktionierenden Datei. | Inventar und Digests passen zum Kandidaten-Commit; zwei Läufe liefern dieselben fachlichen Endzustände und es gibt keine ungeklärte Abweichung mit hoher oder kritischer Priorität. |

## Reihenfolge und Stop-Regeln

Die Aufgaben werden grundsätzlich in Tabellenreihenfolge bearbeitet. 19.3 bis
19.7 dürfen parallel analysiert werden, repariert wird in 19.8 jedoch immer nur
der **erste** belegte Unterschied. Dadurch kann ein Folgefehler nicht die
eigentliche Ursache verdecken. Nach einer Reparatur beginnt die betroffene
Signalkette wieder bei ihrer kleinsten Abnahme; erst danach folgt die volle
Regression.

Folgende Situationen sind kein Grund, eine ältere `.circ`-Datei einzuspielen:

1. Ein Test erwartet eine frühere Bauteilkoordinate.
2. Ein automatisch erzeugtes Diagnoseblatt sieht anders aus.
3. Eine umfassende Matrix endet nur mit einem Timeout.
4. Die Python-VM liefert das erwartete Ergebnis.

Stattdessen ist der Fehler jeweils auf einen benannten Port und die erste
abweichende Flanke einzugrenzen. Diagnoseblätter werden ausschließlich aus der
aktuellen Hauptdatei erzeugt. Die VM ist das fachliche Orakel, aber kein Ersatz
für einen elektrischen Logisim-Lauf.

## Nachweise pro Aufgabe

Jede Aufgabe hinterlässt vier kurze Angaben im Fehlerbericht: **Ausgangslage**,
**Kommando oder Bedienfolge**, **beobachteter Nachweis** und **offene Risiken**.
Binäre oder große Simulatorartefakte gehören in das dafür vorgesehene
Artefaktverzeichnis, nicht ungeprüft in Git. Ein Arbeitsschritt gilt erst dann
als erledigt, wenn sein Abnahmekriterium bestanden hat; „Schaltung sieht
richtig aus“ ist kein Abnahmenachweis.

## Paketgrenze

AP 19 darf Verdrahtungs- und Attributfehler in `TinyCPU.circ`, zugehörige
topologische Regressionstests und die Debug-Anleitung korrigieren. Änderungen
an Opcode-Belegung, Wortformat, VM-Semantik, Profilbreiten sowie die noch offene
Peripherieintegration aus AP 18 liegen außerhalb des Pakets. Zeigt die Analyse
einen solchen Vertragsfehler, wird er als separates Folgepaket vorgeschlagen,
nicht stillschweigend in die Schaltungsreparatur aufgenommen.

# Funktionsstand der TinyCPU-Befehle

**Stand:** 14. September 2026

## Kurzantwort

Der Kernlauf, alle 50 positiven Opcode-Fälle und sämtliche fünf zusätzlichen
Nicht-genommen-Fälle der Logisim-Schaltung sind inzwischen elektrisch
nachgewiesen. Der danach als erster ausgefallene Sticky-Error-Fall
`reserved-opcode` ist korrigiert: Decoderzeile `0x3f` setzt jetzt `ILL` und
löst zugleich den erwarteten Fehlerhalt aus. Sowohl dieser Fall als auch der
anschließende `missing-input`-Fall bestehen in gezielten elektrischen Läufen.
Eine erneute vollständige serielle Profilabnahme steht noch aus.

Diese Aussage betrifft die ausführbare Schaltung
`hardware/logisim/TinyCPU.circ` (16/12 Bit), nicht das Python-Referenzmodell.

## Prüfergebnis

Ausgeführt wurde:

```bash
LOGISIM_JAR=.venv/Include/logisim-evolution-4.1.0-all.jar scripts/test-logisim.sh
```

Ergebnis:

- **16/12-Bit-Profil:** Kernlauf zweimal erfolgreich.
- **Positive Befehlstests:** alle 50 Fälle erfolgreich.
- **Zusätzliche Sprungfälle:** alle fünf Fälle erfolgreich.
- **Sticky-Error-Fälle:** die zuvor erfolgreichen ersten vier Fälle sowie die
  gezielt erneut ausgeführten Fälle `reserved-opcode` und `missing-input`
  erfolgreich.
- **Gesamtergebnis:** vollständige elektrische Profilabnahme nach der Reparatur
  noch nicht erneut ausgeführt.

Die strukturelle Offline-Prüfung der Schaltungsdateien und Verträge ist
erfolgreich. Der vollständige Offline-Lauf enthält derzeit unabhängig von
dieser Reparatur zwei fehlschlagende Topologieprüfungen des `JumpBox`-Blatts.

## Vollständig abgenommene Befehle

**Keine.** Die positiven Einzelfälle und die beiden zuletzt gezielt geprüften
Sticky-Error-Fälle sind zwar erfolgreich, die verbindliche Gesamtabnahme wurde
nach der Reparatur aber noch nicht vollständig wiederholt. Die nachfolgende
Tabelle verwendet deshalb weiterhin den strengen Status „kein vollständiger
elektrischer Nachweis“.

## Befehle, die derzeit nicht als funktionsfähig gelten

| Opcode | Befehl | Status |
|---:|---|---|
| `0x00` | `ADD_CONST` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x01` | `ADD_ADDRESS` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x02` | `ADD_ADDRESS_REGISTER` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x03` | `ADD_ADDRESS_REGISTER_PLUS_OFFSET` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x04` | `SUB_CONST` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x05` | `SUB_ADDRESS` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x06` | `SUB_ADDRESS_REGISTER` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x07` | `SUB_ADDRESS_REGISTER_PLUS_OFFSET` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x08` | `MUL_CONST` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x09` | `MUL_ADDRESS` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x0a` | `MUL_ADDRESS_REGISTER` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x0b` | `MUL_ADDRESS_REGISTER_PLUS_OFFSET` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x0c` | `DIV_CONST` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x0d` | `DIV_ADDRESS` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x0e` | `DIV_ADDRESS_REGISTER` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x0f` | `DIV_ADDRESS_REGISTER_PLUS_OFFSET` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x10` | `AND_CONST` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x11` | `AND_ADDRESS` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x12` | `AND_ADDRESS_REGISTER` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x13` | `AND_ADDRESS_REGISTER_PLUS_OFFSET` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x14` | `OR_CONST` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x15` | `OR_ADDRESS` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x16` | `OR_ADDRESS_REGISTER` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x17` | `OR_ADDRESS_REGISTER_PLUS_OFFSET` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x18` | `XOR_CONST` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x19` | `XOR_ADDRESS` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x1a` | `XOR_ADDRESS_REGISTER` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x1b` | `XOR_ADDRESS_REGISTER_PLUS_OFFSET` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x1c` | `NOT` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x1d` | `JUMP_ADDRESS` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x1e` | `JUMP_ZERO` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x1f` | `JUMP_NOT_ZERO` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x20` | `JUMP_NEGATIVE` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x21` | `JUMP_ERROR` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x22` | `JUMP_NOT_ERROR` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x23` | `LOAD_CONST` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x24` | `LOAD_ADDRESS` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x25` | `LOAD_ADDRESS_REGISTER` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x26` | `LOAD_ADDRESS_REGISTER_PLUS_OFFSET` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x27` | `LOAD_ADDRESS_REGISTER_CONST` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x28` | `LOAD_ADDRESS_REGISTER_ADDRESS` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x29` | `STORE_ADDRESS` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x2a` | `STORE_ADDRESS_REGISTER` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x2b` | `STORE_ADDRESS_REGISTER_PLUS_OFFSET` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x32` | `CLEAR_ERROR` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x33` | `INPUT` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x34` | `PRINT` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x35` | `PRINT_ADDRESS` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x36` | `HALT` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x37` | `HALT_ERROR` | ❌ kein erfolgreicher elektrischer Nachweis |

## Wann darf ein Befehl auf „funktioniert“ gesetzt werden?

Ein Befehl gilt erst dann als funktionsfähig, wenn

1. `scripts/test-offline.sh` erfolgreich ist,
2. der Kernlauf des betreffenden Profils den erwarteten Halt-Zustand erreicht,
3. der isolierte Fall des Befehls aus der elektrischen Matrix erfolgreich
   durch Logisim-evolution läuft und
4. bei bedingten Sprüngen sowohl der genommene als auch der nicht genommene Fall
   erfolgreich ist.

Die Übersicht sollte nach einer Reparatur anhand der automatischen Abnahme neu
erzeugt beziehungsweise aktualisiert werden. Ein rein strukturell vorhandener
Decoder-Ausgang oder ein funktionierender Teilbaustein reicht nicht aus, um
einen vollständigen CPU-Befehl als funktionsfähig einzustufen.

# Funktionsstand der TinyCPU-Befehle

**Stand:** 14. September 2026

## Kurzantwort

Der Kernlauf, alle 50 positiven Opcode-Fälle und die ersten vier zusätzlichen
Nicht-genommen-Fälle der Logisim-Schaltung sind inzwischen elektrisch
nachgewiesen. `JUMP_ZERO` wertet dabei Null und Nicht-Null jetzt korrekt aus.
Die vollständige Abnahme scheitert als nächstes am Fall
`jump-not-error-not-taken`: `JUMP_NOT_ERROR` springt bei gesetztem
Divisionsfehler fälschlich zum `HALT_ERROR`. Weil die Matrix seriell und
Fail-fast läuft, sind die sechs Sticky-Error-Fälle in diesem Lauf noch nicht
erneut geprüft worden.

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
- **Zusätzliche Sprungfälle:** die ersten vier Fälle erfolgreich; der fünfte
  Fall `jump-not-error-not-taken` fehlgeschlagen.
- **Gesamtergebnis:** elektrische Profilabnahme fehlgeschlagen.

Die schnelle Offline-Prüfung ist erfolgreich (82 Tests).

## Vollständig abgenommene Befehle

**Keine.** Die positiven Einzelfälle sind zwar erfolgreich, die verbindliche
Gesamtabnahme ist wegen des zusätzlichen `JUMP_ZERO`-Negativfalls aber noch
nicht vollständig. Die nachfolgende Tabelle verwendet deshalb weiterhin den
strengen Status „kein vollständiger elektrischer Nachweis“.

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

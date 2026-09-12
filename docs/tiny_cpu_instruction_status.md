# Funktionsstand der TinyCPU-Befehle

**Stand:** 12. September 2026, Schaltungsversion `19e2add`

## Kurzantwort

Zurzeit ist **kein Befehl der Logisim-Schaltung als funktionsfähig
nachgewiesen**. Das bedeutet nicht, dass jeder einzelne Befehl zwingend einen
eigenen Defekt hat: Schon der vorgeschaltete Kernlauf erreicht bei beiden
Hardwareprofilen keinen Halt-Zustand. Deshalb startet die Einzelprüfung der
Befehle gar nicht. Ohne einen erfolgreichen Ende-zu-Ende-Test wird ein Befehl
in dieser Übersicht bewusst nicht als „funktioniert“ bezeichnet.

Diese Aussage betrifft die ausführbaren Schaltungen
`hardware/logisim/TinyCPU.circ` (16/12 Bit) und
`hardware/logisim/TinyCPU-8-8.circ` (8/8 Bit), nicht das Python-Referenzmodell.

## Prüfergebnis

Ausgeführt wurde:

```bash
LOGISIM_JAR=.venv/Include/logisim-evolution-4.1.0-all.jar scripts/test-logisim.sh
```

Ergebnis:

- **16/12-Bit-Profil:** Kernlauf nach 90 Sekunden ohne Halt abgebrochen.
- **8/8-Bit-Profil:** Kernlauf nach 90 Sekunden ohne Halt abgebrochen.
- **Einzelne Befehlstests:** nicht gestartet, da der Kernlauf die notwendige
  Vorprüfung ist.
- **Gesamtergebnis:** beide elektrischen Profilabnahmen fehlgeschlagen.

Auch die schnelle Offline-Prüfung ist derzeit nicht erfolgreich:

```text
TinyCPU verification failed: hardware/logisim/TinyCPU-8-8.circ:
legacy 16/12 width remains in width
```

## Befehle, die funktionieren

**Keine.** Gegenwärtig hat kein Befehl einen erfolgreichen elektrischen
Ende-zu-Ende-Nachweis in beiden unterstützten Profilen.

## Befehle, die derzeit nicht als funktionsfähig gelten

| Opcode | Befehl | Status |
|---:|---|---|
| `0x00` | `LOAD_CONST` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x01` | `LOAD_ADDRESS` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x02` | `LOAD_ADDRESS_REGISTER` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x03` | `LOAD_ADDRESS_REGISTER_PLUS_OFFSET` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x04` | `ADD_CONST` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x05` | `ADD_ADDRESS` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x06` | `ADD_ADDRESS_REGISTER` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x07` | `ADD_ADDRESS_REGISTER_PLUS_OFFSET` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x08` | `SUB_CONST` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x09` | `SUB_ADDRESS` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x0a` | `SUB_ADDRESS_REGISTER` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x0b` | `SUB_ADDRESS_REGISTER_PLUS_OFFSET` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x0c` | `MUL_CONST` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x0d` | `MUL_ADDRESS` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x0e` | `MUL_ADDRESS_REGISTER` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x0f` | `MUL_ADDRESS_REGISTER_PLUS_OFFSET` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x10` | `DIV_CONST` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x11` | `DIV_ADDRESS` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x12` | `DIV_ADDRESS_REGISTER` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x13` | `DIV_ADDRESS_REGISTER_PLUS_OFFSET` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x14` | `AND_CONST` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x15` | `AND_ADDRESS` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x16` | `AND_ADDRESS_REGISTER` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x17` | `AND_ADDRESS_REGISTER_PLUS_OFFSET` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x18` | `OR_CONST` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x19` | `OR_ADDRESS` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x1a` | `OR_ADDRESS_REGISTER` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x1b` | `OR_ADDRESS_REGISTER_PLUS_OFFSET` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x1c` | `STORE_ADDRESS` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x1d` | `STORE_ADDRESS_REGISTER` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x1e` | `STORE_ADDRESS_REGISTER_PLUS_OFFSET` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x1f` | `LOAD_ADDRESS_REGISTER_CONST` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x20` | `LOAD_ADDRESS_REGISTER_ADDRESS` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x21` | `NOT` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x22` | `JUMP_ADDRESS` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x23` | `JUMP_ZERO` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x24` | `JUMP_NOT_ZERO` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x25` | `JUMP_NEGATIVE` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x26` | `JUMP_ERROR` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x27` | `JUMP_NOT_ERROR` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x28` | `CLEAR_ERROR` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x29` | `INPUT` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x2a` | `PRINT` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x2b` | `PRINT_ADDRESS` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x2c` | `HALT` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x2d` | `HALT_ERROR` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x2e` | `XOR_CONST` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x2f` | `XOR_ADDRESS` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x30` | `XOR_ADDRESS_REGISTER` | ❌ kein erfolgreicher elektrischer Nachweis |
| `0x31` | `XOR_ADDRESS_REGISTER_PLUS_OFFSET` | ❌ kein erfolgreicher elektrischer Nachweis |

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

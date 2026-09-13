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

# Funktionsstand der TinyCPU-Befehle

**Stand:** 14. September 2026

## Kurzantwort

Der Kernlauf, alle 50 positiven Opcode-Fälle, sämtliche fünf zusätzlichen
Nicht-genommen-Fälle und alle sechs Sticky-Error-Fälle der Logisim-Schaltung
sind inzwischen in einer vollständigen elektrischen Profilabnahme
nachgewiesen. Der dabei identifizierte, nicht funktionierende Befehl war
`HALT_ERROR` (`0x37`): Seine Decoderleitung endete zwischen den Eingängen des
gemeinsamen Fehlerhalt-ODER-Gatters. Die Leitung erreicht nun einen echten
Gattereingang; auch der reservierte Opcode `0x3f` setzt weiterhin `ILL` und
löst den erwarteten Fehlerhalt aus.

Diese Aussage betrifft die ausführbare Schaltung
`hardware/logisim/TinyCPU.circ` (16/12 Bit), nicht das Python-Referenzmodell.

## Prüfergebnis

Ausgeführt wurde:

```bash
LOGISIM_JOBS=4 LOGISIM_JAR=.venv/Include/logisim-evolution-4.1.0-all.jar scripts/test-logisim.sh
```

Ergebnis:

- **16/12-Bit-Profil:** Kernlauf zweimal erfolgreich.
- **Positive Befehlstests:** alle 50 Fälle erfolgreich.
- **Zusätzliche Sprungfälle:** alle fünf Fälle erfolgreich.
- **Sticky-Error-Fälle:** alle sechs Fälle erfolgreich.
- **Gesamtergebnis:** vollständige elektrische Profilabnahme mit 61 Fixtures
  erfolgreich.

Auch die strukturelle Offline-Prüfung der Schaltungsdateien, Verträge und
benannten `JumpBox`-Verbindungen ist erfolgreich. Zwei Topologieprüfungen
waren noch an veraltete Zeichenkoordinaten gebunden und meldeten nach einer
reinen Layoutänderung fälschlich einen Defekt. Sie verfolgen die Leitungen nun
zwischen den benannten Pins und Gattern.

## Vollständig abgenommene Befehle

Alle 50 in der nachfolgenden Tabelle aufgeführten Befehle sind elektrisch und
strukturell abgenommen. Bei der Suche nach dem nächsten nicht funktionierenden
Befehl wurde daher kein weiterer Befehlsfehler gefunden.

## Funktionsfähige Befehle

| Opcode | Befehl | Status |
|---:|---|---|
| `0x00` | `ADD_CONST` | ✅ vollständig abgenommen |
| `0x01` | `ADD_ADDRESS` | ✅ vollständig abgenommen |
| `0x02` | `ADD_ADDRESS_REGISTER` | ✅ vollständig abgenommen |
| `0x03` | `ADD_ADDRESS_REGISTER_PLUS_OFFSET` | ✅ vollständig abgenommen |
| `0x04` | `SUB_CONST` | ✅ vollständig abgenommen |
| `0x05` | `SUB_ADDRESS` | ✅ vollständig abgenommen |
| `0x06` | `SUB_ADDRESS_REGISTER` | ✅ vollständig abgenommen |
| `0x07` | `SUB_ADDRESS_REGISTER_PLUS_OFFSET` | ✅ vollständig abgenommen |
| `0x08` | `MUL_CONST` | ✅ vollständig abgenommen |
| `0x09` | `MUL_ADDRESS` | ✅ vollständig abgenommen |
| `0x0a` | `MUL_ADDRESS_REGISTER` | ✅ vollständig abgenommen |
| `0x0b` | `MUL_ADDRESS_REGISTER_PLUS_OFFSET` | ✅ vollständig abgenommen |
| `0x0c` | `DIV_CONST` | ✅ vollständig abgenommen |
| `0x0d` | `DIV_ADDRESS` | ✅ vollständig abgenommen |
| `0x0e` | `DIV_ADDRESS_REGISTER` | ✅ vollständig abgenommen |
| `0x0f` | `DIV_ADDRESS_REGISTER_PLUS_OFFSET` | ✅ vollständig abgenommen |
| `0x10` | `AND_CONST` | ✅ vollständig abgenommen |
| `0x11` | `AND_ADDRESS` | ✅ vollständig abgenommen |
| `0x12` | `AND_ADDRESS_REGISTER` | ✅ vollständig abgenommen |
| `0x13` | `AND_ADDRESS_REGISTER_PLUS_OFFSET` | ✅ vollständig abgenommen |
| `0x14` | `OR_CONST` | ✅ vollständig abgenommen |
| `0x15` | `OR_ADDRESS` | ✅ vollständig abgenommen |
| `0x16` | `OR_ADDRESS_REGISTER` | ✅ vollständig abgenommen |
| `0x17` | `OR_ADDRESS_REGISTER_PLUS_OFFSET` | ✅ vollständig abgenommen |
| `0x18` | `XOR_CONST` | ✅ vollständig abgenommen |
| `0x19` | `XOR_ADDRESS` | ✅ vollständig abgenommen |
| `0x1a` | `XOR_ADDRESS_REGISTER` | ✅ vollständig abgenommen |
| `0x1b` | `XOR_ADDRESS_REGISTER_PLUS_OFFSET` | ✅ vollständig abgenommen |
| `0x1c` | `NOT` | ✅ vollständig abgenommen |
| `0x1d` | `JUMP_ADDRESS` | ✅ vollständig abgenommen |
| `0x1e` | `JUMP_ZERO` | ✅ vollständig abgenommen |
| `0x1f` | `JUMP_NOT_ZERO` | ✅ vollständig abgenommen |
| `0x20` | `JUMP_NEGATIVE` | ✅ vollständig abgenommen |
| `0x21` | `JUMP_ERROR` | ✅ vollständig abgenommen |
| `0x22` | `JUMP_NOT_ERROR` | ✅ vollständig abgenommen |
| `0x23` | `LOAD_CONST` | ✅ vollständig abgenommen |
| `0x24` | `LOAD_ADDRESS` | ✅ vollständig abgenommen |
| `0x25` | `LOAD_ADDRESS_REGISTER` | ✅ vollständig abgenommen |
| `0x26` | `LOAD_ADDRESS_REGISTER_PLUS_OFFSET` | ✅ vollständig abgenommen |
| `0x27` | `LOAD_ADDRESS_REGISTER_CONST` | ✅ vollständig abgenommen |
| `0x28` | `LOAD_ADDRESS_REGISTER_ADDRESS` | ✅ vollständig abgenommen |
| `0x29` | `STORE_ADDRESS` | ✅ vollständig abgenommen |
| `0x2a` | `STORE_ADDRESS_REGISTER` | ✅ vollständig abgenommen |
| `0x2b` | `STORE_ADDRESS_REGISTER_PLUS_OFFSET` | ✅ vollständig abgenommen |
| `0x32` | `CLEAR_ERROR` | ✅ vollständig abgenommen |
| `0x33` | `INPUT` | ✅ vollständig abgenommen |
| `0x34` | `PRINT` | ✅ vollständig abgenommen |
| `0x35` | `PRINT_ADDRESS` | ✅ vollständig abgenommen |
| `0x36` | `HALT` | ✅ vollständig abgenommen |
| `0x37` | `HALT_ERROR` | ✅ vollständig abgenommen |

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

# Im Projekt enthaltene Logisim-Laufzeitabhängigkeit

Logisim-evolution gehört als fest gepinnte und automatisch verwaltete
Laufzeitabhängigkeit zum TinyCPU-Projekt. Schaltungen, Profile, elektrische
Fixtures und der Launcher sind eingecheckt. Nur das unveränderte große
Upstream-JAR wird nicht als Git-Blob dupliziert. Der Launcher prüft zuerst
diesen vorbereiteten Vendor-Pfad:

```text
vendor/logisim-evolution-4.1.0-all.jar
```

Liegt das exakte Upstream-JAR dort, laufen die elektrischen Tests vollständig
ohne Netzwerkzugriff. Andernfalls prüft `src/tiny_cpu_logisim.py` als Nächstes
`~/.cache/tinycpu/` und lädt dieselbe festgelegte Version nur als letzte
Möglichkeit herunter. GitHub Actions cached diese Projektabhängigkeit zwischen
den Läufen.

Das JAR wird absichtlich nicht durch einen leeren Platzhalter dargestellt: Ist
die Datei vorhanden, muss sie immer ein echtes Java-Archiv für die elektrische
Abnahme sein.

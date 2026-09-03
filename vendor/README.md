# Logisim runtime

The repository does not currently contain the Logisim-evolution binary. The
launcher nevertheless checks this directory first for the pinned file:

```text
vendor/logisim-evolution-4.1.0-all.jar
```

Place that exact upstream JAR at this path to run the electrical tests without
network access. If it is absent, `src/tiny_cpu_logisim.py` next checks
`~/.cache/tinycpu/` and downloads the same pinned release only as a last resort.
GitHub Actions caches that download between runs.

The JAR is intentionally not represented by an empty placeholder: its presence
must always mean that a real Java archive is available to the electrical gate.

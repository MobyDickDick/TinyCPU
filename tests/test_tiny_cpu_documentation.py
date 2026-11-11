"""Run the published examples and check links on the current entry pages."""
from __future__ import annotations

import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import unittest
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
CURRENT_PAGES = (
    "docs/README.md", "docs/tiny_cpu_quickstart.md", "docs/tiny_cpu.md",
    "docs/tiny_cpu_test_guide.md", "docs/tiny_cpu_debugger.md",
    "docs/tiny_cpu_instruction_status.md", "docs/tiny_cpu_development_directions.md",
    "docs/tiny_cpu_peripherals.md", "docs/tiny_cpu_compatibility.md",
    "docs/tiny_cpu_core_trace.md", "hardware/logisim/README.md",
    "hardware/logisim/TinyCPU.md", "hardware/logisim/TinyCPU_Operator.md",
    "hardware/logisim/TinyCPU_Peripherals.md", "vendor/README.md",
)
EXAMPLE = re.compile(
    r"<!-- example: ([\w-]+) exit: (\d+) -->\s*"
    r"```bash\n([^`]+)```\s*```text\n([^`]+)```"
)


class DocumentationTests(unittest.TestCase):
    def test_published_program_runs(self) -> None:
        found = set()
        env = os.environ.copy()
        # A fresh checkout must not depend on an installed TinyCPU or PYTHONPATH.
        env.pop("PYTHONPATH", None)
        for page in ("docs/tiny_cpu_quickstart.md", "docs/tiny_cpu.md"):
            for match in EXAMPLE.finditer((ROOT / page).read_text(encoding="utf-8")):
                name, code, command, expected = match.groups()
                self.assertNotIn(name, found)
                found.add(name)
                args = shlex.split(command.strip())
                self.assertEqual(args[:2], ["python", "src/tiny_cpu_debugger.py"])
                with self.subTest(page=page, example=name):
                    run = subprocess.run(
                        [sys.executable, *args[1:]], cwd=ROOT, env=env,
                        text=True, capture_output=True, timeout=30,
                    )
                    self.assertEqual(run.returncode, int(code), run.stderr)
                    self.assertEqual(run.stderr, "")
                    self.assertEqual(run.stdout, expected)
        self.assertEqual(found, {"countdown", "sum", "input", "missing-input", "breakpoint", "error-halt"})

    def test_current_documentation_local_links(self) -> None:
        for name in CURRENT_PAGES:
            page = ROOT / name
            # Ignore examples in fences; check inline Markdown file/fragment links.
            source = re.sub(r"```.*?```", "", page.read_text(encoding="utf-8"), flags=re.S)
            for target in re.findall(r"\[[^\]\n]+\]\(([^)\s]+)\)", source):
                url = urlsplit(target.strip("<>"))
                if url.scheme or url.netloc:
                    continue
                path = (page.parent / unquote(url.path)).resolve() if url.path else page
                with self.subTest(page=name, target=target):
                    self.assertTrue(path.is_relative_to(ROOT), "link escapes checkout")
                    self.assertTrue(path.exists(), f"missing local target: {target}")
                    if url.fragment and path.suffix == ".md" and path.exists():
                        headings = re.findall(r"^#{1,6}\s+(.+)$", path.read_text(encoding="utf-8"), re.M)
                        slugs = {re.sub(r"[^\w\- ]", "", h.lower()).replace(" ", "-") for h in headings}
                        self.assertIn(unquote(url.fragment), slugs, "missing heading anchor")


if __name__ == "__main__":
    unittest.main()

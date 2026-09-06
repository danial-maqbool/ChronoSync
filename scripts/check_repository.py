"""Check tracked and proposed public files without scanning private data directories."""

import re
import subprocess
from pathlib import Path

paths = (
    subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
    )
    .decode()
    .split("\0")
)
bad = []
pattern = re.compile(
    rb"\b(?:gh[pousr]_[A-Za-z0-9]{25,}|AIza[0-9A-Za-z_-]{30,}|sk-[A-Za-z0-9]{30,})\b|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
)
for name in set(filter(None, paths)):
    p = Path(name)
    if (
        name.startswith(("data/", "uploads/", "exports/", "tokens/", ".venv/"))
        or p.suffix in {".db", ".sqlite", ".eml", ".msg"}
        or (p.name.startswith(".env") and p.name != ".env.example")
    ):
        bad.append(name + ": private artifact in public file set")
    if p.is_file() and p.suffix != ".png" and pattern.search(p.read_bytes()):
        bad.append(name + ": credential-like content detected")
if bad:
    print("\n".join(bad))
    raise SystemExit(1)
print(
    "Public file set checked: no forbidden private artifacts or recognized credential patterns."
)

from __future__ import annotations

import re
from pathlib import Path

PATTERNS = {
    "private key": re.compile(r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY"),
    "Google API key": re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    "OpenAI key": re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
}
SKIP = {".git", ".venv", "node_modules", "data"}

failures = []
for path in Path('.').rglob('*'):
    if not path.is_file() or any(part in SKIP for part in path.parts):
        continue
    if path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.gif', '.zip', '.db'}:
        continue
    try: text = path.read_text(encoding='utf-8')
    except UnicodeDecodeError: continue
    for label, pattern in PATTERNS.items():
        if pattern.search(text): failures.append(f"{label}: {path}")
if failures:
    raise SystemExit("Potential secrets detected:\n" + "\n".join(failures))
print("Secret-pattern scan passed.")

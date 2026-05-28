"""After pip install on Windows embeddable Python: ensure site-packages is on sys.path."""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    py_dir = root / "python"
    if not (py_dir / "python.exe").is_file():
        return

    site = py_dir / "Lib" / "site-packages"
    if not site.is_dir():
        print("warn: no Lib/site-packages yet", file=sys.stderr)
        return

    pth_files = list(py_dir.glob("python*._pth"))
    if not pth_files:
        return
    pth = pth_files[0]
    lines = pth.read_text(encoding="utf-8").splitlines()
    rel = "Lib\\site-packages"
    if not any(rel.replace("\\", "/") in ln.replace("\\", "/") for ln in lines):
        # insert before import site if present, else append
        out: list[str] = []
        inserted = False
        for ln in lines:
            if not inserted and ln.strip() == "import site":
                out.append(rel)
                inserted = True
            out.append(ln)
        if not inserted:
            out.append(rel)
        if not any(ln.strip() == "import site" for ln in out):
            out.append("import site")
        pth.write_text("\n".join(out) + "\n", encoding="utf-8")
        print("patched", pth.name, "with", rel)


if __name__ == "__main__":
    main()

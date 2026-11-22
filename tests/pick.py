"""Run only the tests that cover what changed since origin/main.

    python tests/pick.py            # changed tests only, full site builds skipped
    python tests/pick.py --slow     # same, plus the full site builds
    python tests/pick.py --list     # show the picked files, run nothing

A changed aipulse module picks every test file that imports it, or imports a module
that imports it. Template or CSS changes pick the site tests. Anything else
(requirements, conftest, helpers, fixtures, data, a new folder) runs every test file.
Docs, Actions files, git hooks and Apps Script never pick tests.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
PKG = ROOT / "aipulse"
HUBS = {"__main__", "pages", "static", "server"}  # import nearly everything; covered by the --slow builds


def changed_files():
    git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    return set(git("diff", "--name-only", "origin/main...HEAD")) | set(git("diff", "--name-only", "HEAD")) \
        | set(git("ls-files", "--others", "--exclude-standard"))


def imported_modules(text, modules):
    """aipulse modules a file uses: `from aipulse import a, b`, `from aipulse.a import`, `aipulse.a`, `from . import a`."""
    found = set()
    for m in re.finditer(r"from\s+(?:aipulse|\.)\s+import\s+\(?([\w\s,]+)", text):
        found |= {part.split()[0] for part in m.group(1).split(",") if part.strip()}
    found |= set(re.findall(r"aipulse\.(\w+)", text)) | set(re.findall(r"from\s+\.(\w+)\s+import", text))
    return found & modules


def module_users():
    """For each module, itself plus the modules that import it directly (one step, not the whole chain:
    the command line and page builder import nearly everything, so the full chain would pick every test)."""
    files = {p.stem: p for p in PKG.glob("*.py")}
    files |= {p.name: p / "__init__.py" for p in PKG.iterdir() if (p / "__init__.py").is_file()}
    modules = set(files)
    users = {m: {m} for m in modules}
    for m, f in files.items():
        if m in HUBS:
            continue
        for d in imported_modules(f.read_text(encoding="utf-8"), modules):
            users[d].add(m)
    return users, modules


def pick(paths):
    """Test files to run, or None for all of them."""
    users, modules = module_users()
    tests = {p: imported_modules(p.read_text(encoding="utf-8"), modules) for p in TESTS.glob("test_*.py")}
    picked = set()
    for path in paths:
        parts = Path(path).parts
        if parts[0] == "tests" and len(parts) == 2 and parts[1].startswith("test_") and path.endswith(".py"):
            if (ROOT / path).exists():
                picked.add(ROOT / path)
        elif parts[0] == "aipulse" and path.endswith(".py"):
            mod = parts[1] if len(parts) > 2 else Path(parts[1]).stem
            if mod in ("__init__", "config"):
                return None
            hit = users.get(mod, {mod})
            picked |= {t for t, used in tests.items() if used & hit}
        elif parts[0] == "templates" or path.endswith(".css") or path.endswith(".js"):
            picked.add(TESTS / "test_site.py")
        elif parts[0] in (".claude", ".github", "apps-script", "hooks") or (len(parts) == 1 and path.endswith(".md")):
            continue
        else:
            return None
    return sorted(picked)


def main():
    args = sys.argv[1:]
    files = pick(changed_files())
    if files is None:
        targets, label = ["tests"], "every test file"
    elif not files:
        print("Nothing changed that the tests cover.")
        return 0
    else:
        targets = [str(f.relative_to(ROOT)) for f in files]
        label = ", ".join(Path(t).name for t in targets)
    print(f"Running: {label}" + ("" if "--slow" in args else " (full site builds skipped; add --slow for them)"))
    if "--list" in args:
        return 0
    return subprocess.run([sys.executable, "-m", "pytest", "-n", "auto", "-q", *targets,
                           *[a for a in args if a != "--list"]], cwd=ROOT).returncode


if __name__ == "__main__":
    sys.exit(main())

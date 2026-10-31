"""AI Pulse: a self-hosted tracker for AI releases, industry news and policy."""
from pathlib import Path

# Pulse Compass, the paid product, lives in a private repo: its modules join this package when that repo is checked out
# as compass/ in this folder (the site's build, the Compass routines) or as ai-pulse-compass/ beside it (the owner's PC).
_ROOT = Path(__file__).resolve().parents[1]
COMPASS = next((str(c) for c in (_ROOT / "compass" / "aipulse", _ROOT.parent / "ai-pulse-compass" / "aipulse")
                if c.is_dir()), "")
if COMPASS:
    __path__.append(COMPASS)

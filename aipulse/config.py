"""Every setting and secret AI Pulse reads from its environment, in one place.

On GitHub Actions they come from the repo's secrets (Settings > Secrets and variables > Actions), passed to each step in
the workflow's `env:`; on a PC, from the shell. Nothing here has a value written in: an unset secret switches its feature
off quietly (the site still builds). Each is read when it is used, not when the module loads, so a test can set it.

Secrets (repo secrets)
  DIGEST_EMAIL          the project's Gmail address: sends the emails and receives the notes to approve
  DIGEST_APP_PASSWORD   that Gmail account's app password
  DIGEST_LIST_KEY       the key for the readers' list (the Apps Script web app); sent in a POST body, never a URL
  DIGEST_SIGNUP_URL     the address of that web app
  COMPASS_USERS         Pulse Compass's users: salts and derived keys, no passwords (aipulse/access.py)
  CONGRESS_API_KEY      congress.gov's free API, for US bills
  GITHUB_TOKEN          GitHub's API: labs' new repositories (set by Actions itself)
  GEMINI_API_KEY        the weekly meme's and the poster's wording; without it the rule-based versions are used
  ANTHROPIC_API_KEY,    the labs' free model lists only (sources.py `key_env`); skipped while unset
  OPENAI_API_KEY

Settings
  GEMINI_MODEL          which Gemini model (default: Google's newest Flash)
  AIPULSE_OFFLINE       set by the tests: never download, use only what is cached
  GITHUB_REPOSITORY,    set by Actions itself: which repo and branch a run is on (a sample email from another branch
  GITHUB_REF_NAME       links that branch's pictures)
"""
from __future__ import annotations

import os

REPO = "shru14/ai-pulse"  # this repository on GitHub: where `compass-user` saves the secret and starts a rebuild


def secret(name: str) -> str:
    """Any one of the secrets above by name ("" when unset); for code that picks the name itself, like a source's key."""
    return os.environ.get(name, "")


def digest_email() -> str:
    return secret("DIGEST_EMAIL").strip()


def digest_app_password() -> str:
    return secret("DIGEST_APP_PASSWORD").replace(" ", "")  # Google shows it in groups of four


def digest_list_key() -> str:
    return secret("DIGEST_LIST_KEY")


def digest_signup_url() -> str:
    return secret("DIGEST_SIGNUP_URL")


def compass_users() -> str:
    return secret("COMPASS_USERS")


def congress_key() -> str:
    return secret("CONGRESS_API_KEY")


def github_token() -> str:
    return secret("GITHUB_TOKEN")


def gemini_key() -> str:
    return secret("GEMINI_API_KEY")


def gemini_model() -> str:
    return os.environ.get("GEMINI_MODEL", "gemini-flash-latest")  # always Google's newest Flash model


def offline() -> bool:
    return bool(os.environ.get("AIPULSE_OFFLINE"))


def github_repository() -> str:
    return os.environ.get("GITHUB_REPOSITORY", REPO)


def github_ref() -> str:
    return os.environ.get("GITHUB_REF_NAME", "main")

"""Loaded by pytest before any test file."""
import os

os.environ["AIPULSE_OFFLINE"] = "1"  # brand logos and models: cached data only, no network

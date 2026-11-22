"""Loaded by pytest before any test file."""
import os

import pytest

os.environ["AIPULSE_OFFLINE"] = "1"  # brand logos and models: cached data only, no network


def pytest_addoption(parser):
    parser.addoption("--slow", action="store_true", help="also run the full site-build tests (several minutes)")


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: builds the whole site; skipped unless --slow is given")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--slow"):
        return
    skip = pytest.mark.skip(reason="full site build: run with --slow")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)

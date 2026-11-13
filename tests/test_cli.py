"""The command line's jobs."""
from pathlib import Path


FIX = Path(__file__).parent / "fixtures"


def test_command_line_entry_point_starts(tmp_path):
    # The scheduled tasks run `python -m aipulse ...`; a syntax error there would stop every collection.
    import subprocess, sys
    root = Path(__file__).parent.parent
    run = lambda *a: subprocess.run([sys.executable, "-m", "aipulse", "--db", str(tmp_path / "t.db"), *a],
                                    cwd=root, capture_output=True, text=True, timeout=60)
    assert run("--help").returncode == 0
    result = run("sources")
    assert result.returncode == 0 and "sources checked" in result.stdout
    result = run("build", "--out", str(tmp_path / "site"))
    assert result.returncode == 0 and (tmp_path / "site" / "data.json").exists()
    # An import inside main() makes that name local to all of main(), so the other commands crash on it
    # (UnboundLocalError); collect can't run here (network), so check for it directly.
    from aipulse import __main__ as cli
    code = cli.main.__code__
    assert not set(code.co_varnames + code.co_cellvars) & set(vars(cli)), "a module-level name is re-imported in main()"


def test_daily_candidate_commands_run(tmp_path, monkeypatch, capsys):
    """The daily routines' to-check lists; the Compass two are tested in its own repo's checkout."""
    from aipulse import __main__ as cli
    data = tmp_path / "data.json"
    data.write_text('{"cards": []}', encoding="utf-8")
    for cmd in ("court", "press", "safety", "infra", "owners", "releases", "timelines", "economy", "pacts", "tests", "fines",
                "chips", "buyouts"):
        monkeypatch.setattr("sys.argv", ["aipulse", cmd, "--data", str(data)])
        cli.main()
        assert capsys.readouterr().out, cmd


def test_quick_run_reads_only_lab_blogs(tmp_path, monkeypatch):
    import sys
    from aipulse import __main__ as cli
    seen = {}
    monkeypatch.setattr(cli, "collect", lambda conn, sources, max_age_days: seen.setdefault("sources", sources) and 0)
    monkeypatch.setattr(sys, "argv", ["aipulse", "--db", str(tmp_path / "t.db"), "collect", "--labs"])
    cli.main()
    assert seen["sources"] and {s["category"] for s in seen["sources"]} == {"tool"}
    assert "Google DeepMind Blog" in {s["name"] for s in seen["sources"]}

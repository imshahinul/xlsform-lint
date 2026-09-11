"""Qualify wheel and sdist installs without invoking publication services."""

from __future__ import annotations

import argparse
import email
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile


VERSION = "0.2.0"
ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "corpus"
EXPECTED_RULES = {
    "PX001", "PX002", "PX003", "PX004", "PX005", "PX006", "PX999",
    "CHO001", "LBL001", "LBL002", "I18N001", "UX001", "ORD001", "UX002",
}


def run(command: list[str], *, cwd: Path, expected: int = 0) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(command, cwd=cwd, env=environment, text=True, capture_output=True)
    if result.returncode != expected:
        raise RuntimeError(
            f"expected exit {expected}, got {result.returncode}: {command!r}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def executables(environment: Path) -> tuple[Path, Path]:
    directory = environment / ("Scripts" if os.name == "nt" else "bin")
    return directory / ("python.exe" if os.name == "nt" else "python"), directory / (
        "xlsform-lint.exe" if os.name == "nt" else "xlsform-lint"
    )


def metadata_and_contents(wheel: Path, sdist: Path) -> None:
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        metadata_name = next(name for name in names if name.endswith(".dist-info/METADATA"))
        entry_name = next(name for name in names if name.endswith(".dist-info/entry_points.txt"))
        metadata = email.message_from_bytes(archive.read(metadata_name))
        assert "xlsform_lint/__init__.py" in names
        assert "xlsform_lint/cli.py" in names
        assert "xlsform-lint = xlsform_lint.cli:main" in archive.read(entry_name).decode()
        assert not any("__pycache__" in name or ".pytest_cache" in name for name in names)
    assert metadata["Name"] == "xlsform-lint"
    assert metadata["Version"] == VERSION
    assert metadata["Requires-Python"] == ">=3.11"
    assert set(metadata.get_all("Requires-Dist", [])) >= {
        "pyxform<4.6,>=4.5", "openpyxl==3.1.5",
    }
    assert metadata["License-Expression"] == "Apache-2.0"
    assert metadata["Summary"]
    assert metadata.get_payload().strip()

    with tarfile.open(sdist, "r:gz") as archive:
        names = set(archive.getnames())
        root = f"xlsform_lint-{VERSION}"
        for expected in (
            "LICENSE", "README.md", "pyproject.toml", "src/xlsform_lint/__init__.py",
            "src/xlsform_lint/cli.py",
        ):
            assert f"{root}/{expected}" in names
        assert not any("__pycache__" in name or ".pytest_cache" in name for name in names)


def qualify(artifact: Path, label: str, workspace: Path) -> dict[str, object]:
    environment = workspace / f"{label}-venv"
    work = workspace / f"{label}-work"
    venv.EnvBuilder(with_pip=True).create(environment)
    work.mkdir()
    python, cli = executables(environment)
    run([str(python), "-m", "pip", "install", str(artifact)], cwd=work)
    run([str(python), "-m", "pip", "check"], cwd=work)
    details = json.loads(run([
        str(python), "-c",
        "import json,os,sys,xlsform_lint; print(json.dumps({'executable':sys.executable,"
        "'package':xlsform_lint.__file__,'version':xlsform_lint.__version__,'cwd':os.getcwd(),"
        "'sys_path':sys.path}))",
    ], cwd=work).stdout)
    assert details["version"] == VERSION
    assert str(ROOT.resolve()) not in details["sys_path"]
    assert str(ROOT.resolve()) not in details["package"]
    assert "site-packages" in details["package"]
    assert Path(details["cwd"]).resolve() == work.resolve()
    run([str(cli), "--help"], cwd=work)

    cases = {
        "clean": (FIXTURES / "valid" / "basic_clean.xlsx", [], 0, set()),
        "native": (
            FIXTURES / "findings" / "mixed_native_findings.xlsx",
            ["--select", "CHO,LBL,I18N,UX,ORD", "--fail-on", "info"], 1, None,
        ),
        "px006": (
            FIXTURES / "findings" / "duplicate_choice.xlsx", ["--select", "PX006"], 1, {"PX006"},
        ),
        "px999": (
            FIXTURES / "malformed" / "unmatched_end_group.xlsx", ["--select", "PX999"], 1, {"PX999"},
        ),
    }
    results: dict[str, object] = {"details": details, "cli": str(cli), "cases": {}}
    for name, (source, options, exit_code, required) in cases.items():
        target = work / source.name
        shutil.copy2(source, target)
        payload = json.loads(run(
            [str(cli), str(target), *options, "--format", "json"], cwd=work, expected=exit_code
        ).stdout)
        ids = {item["rule_id"] for item in payload["diagnostics"]}
        assert payload["version"] == 1
        assert ids <= EXPECTED_RULES
        if required is not None:
            assert required <= ids
        results["cases"][name] = {"exit": exit_code, "rules": sorted(ids), "count": len(ids)}

    sarif = json.loads(run([
        str(cli), str(work / "basic_clean.xlsx"), "--format", "sarif",
    ], cwd=work).stdout)
    assert sarif["version"] == "2.1.0"
    results["json_version"] = 1
    results["sarif_version"] = sarif["version"]
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dist", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    wheel = next(args.dist.glob(f"xlsform_lint-{VERSION}-py3-none-any.whl"))
    sdist = next(args.dist.glob(f"xlsform_lint-{VERSION}.tar.gz"))
    metadata_and_contents(wheel, sdist)
    with tempfile.TemporaryDirectory(prefix="xlsform-lint-qualification-") as temporary:
        workspace = Path(temporary)
        wheel_result = qualify(wheel.resolve(), "wheel", workspace)
        sdist_result = qualify(sdist.resolve(), "sdist", workspace)
    comparable = ("cases", "json_version", "sarif_version")
    assert all(wheel_result[key] == sdist_result[key] for key in comparable)
    report = {"version": VERSION, "wheel": wheel_result, "sdist": sdist_result, "parity": True}
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.report:
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())

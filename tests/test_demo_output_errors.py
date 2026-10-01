"""The demo CLIs refuse old output trees without obscuring later failures."""

import errno
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = (
    ROOT / "examples/canonical-artifacts/roundtrip.py",
    ROOT / "examples/callable-artifacts/demo.py",
)


@pytest.fixture(params=EXAMPLES, ids=("canonical", "callable"))
def demo(request):
    spec = importlib.util.spec_from_file_location("output_error_demo", request.param)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_cli(demo, output, cwd):
    # Isolated child interpreters cannot pick up user site packages or PYTHONPATH.
    bootstrap = (
        "import runpy, sys; "
        "sys.path.insert(0, sys.argv.pop(1)); "
        "script = sys.argv.pop(1); "
        "sys.argv[0] = script; "
        "runpy.run_path(script, run_name='__main__')"
    )
    return subprocess.run(
        [sys.executable, "-I", "-B", "-c", bootstrap, str(ROOT / "src"),
         demo.__file__, "--output", str(output)],
        cwd=cwd, capture_output=True, text=True, timeout=20, check=False,
    )


def snapshot(root):
    """Compare bytes, link text, identity and metadata without following links."""
    result = {}
    for path in [root, *sorted(root.rglob("*"))]:
        info = path.lstat()
        content = (os.readlink(path) if path.is_symlink()
                   else path.read_bytes() if path.is_file() else None)
        result[str(path.relative_to(root))] = (
            info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, content,
        )
    return result


@pytest.fixture(params=("directory", "file", "dangling-link", "directory-link", "file-link"))
def existing_output(request, tmp_path):
    output = tmp_path / "existing output"
    kind = request.param
    if kind == "directory":
        output.mkdir()
        (output / "nested").mkdir()
        (output / "nested/keep.bin").write_bytes(b"old artifact\x00\xff\n")
    elif kind == "file":
        output.write_bytes(b"prior file\x00\xff\n")
    else:
        target = tmp_path / "target"
        if kind == "directory-link":
            target.mkdir()
            (target / "keep.bin").write_bytes(b"prior linked artifact\n")
        elif kind == "file-link":
            target.write_bytes(b"prior linked file\n")
        try:
            output.symlink_to(target.name, target_is_directory=kind == "directory-link")
        except (NotImplementedError, OSError) as exc:
            pytest.skip(f"symlinks unavailable: {exc}")
    return output


def assert_collision(result, output):
    assert result.returncode == 2
    assert result.stdout == ""
    assert "already exists" in result.stderr
    assert "choose a fresh path" in result.stderr
    assert str(output) in result.stderr
    assert "Traceback" not in result.stderr
    assert "FileExistsError" not in result.stderr


def test_cli_refuses_existing_output_without_mutation(demo, existing_output, tmp_path):
    before = snapshot(tmp_path)
    result = run_cli(demo, existing_output, tmp_path)
    assert_collision(result, existing_output)
    assert snapshot(tmp_path) == before


def test_direct_demonstrate_keeps_file_exists_error(demo, existing_output, tmp_path):
    before = snapshot(tmp_path)
    with pytest.raises(FileExistsError) as caught:
        demo.demonstrate(existing_output)
    assert type(caught.value) is FileExistsError
    assert caught.value.filename == str(existing_output)
    assert snapshot(tmp_path) == before


def test_success_output_and_prior_artifacts_survive_repeated_cli(demo, tmp_path):
    output = tmp_path / "new output"
    first = run_cli(demo, output, tmp_path)
    assert first.returncode == 0, first.stderr
    assert first.stderr == ""
    report = json.loads(first.stdout)
    assert first.stdout == json.dumps(report, indent=2, sort_keys=True) + "\n"
    if "passed" in report:
        assert report["passed"] is True
        assert all(report["checks"].values())
        assert report["scientific_accepted"] is False
        assert report["device_control_authorized"] is False
    else:
        assert report["synthetic_software_assertions_passed"] is True
        assert report["success"]["receipt"]["status"] == "COMPLETED"
        assert report["semantic_refusal"]["receipt"]["status"] == "FAILED"
        assert report["permission_refusal"]["receipt"]["status"] == "BLOCKED"
    before = snapshot(tmp_path)
    assert_collision(run_cli(demo, output, tmp_path), output)
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("error_type", (FileExistsError, RuntimeError))
def test_later_error_propagates_with_effects_retained(demo, tmp_path, monkeypatch, capsys,
                                                    error_type):
    output = tmp_path / "new output"
    marker = output / "partial-effect.bin"
    # Even the same filename must not turn a later failure into CLI path advice.
    error = (FileExistsError(errno.EEXIST, "synthetic internal failure", str(output))
             if error_type is FileExistsError else RuntimeError("synthetic internal failure"))
    calls = []

    def fail_after_effect(root, **kwargs):
        assert output.is_dir()
        calls.append(root)
        marker.write_bytes(b"retained effect\n")
        raise error

    internal_step = "run_case" if hasattr(demo, "run_case") else "ArtifactStore"
    monkeypatch.setattr(demo, internal_step, fail_after_effect)
    monkeypatch.setattr(sys, "argv", [demo.__file__, "--output", str(output)])
    with pytest.raises(error_type) as caught:
        demo.main()
    assert caught.value is error
    assert len(calls) == 1
    assert marker.read_bytes() == b"retained effect\n"
    assert list(output.iterdir()) == [marker]
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


def test_missing_parent_is_not_reported_as_collision(demo, tmp_path):
    output = tmp_path / "missing" / "output"
    result = run_cli(demo, output, tmp_path)
    assert result.returncode != 0
    assert result.stdout == ""
    assert "FileNotFoundError" in result.stderr
    assert "choose a fresh path" not in result.stderr
    assert list(tmp_path.iterdir()) == []


def test_failed_assertions_keep_json_and_nonzero_status(demo, tmp_path, monkeypatch, capsys):
    report = {"passed": False, "synthetic_software_assertions_passed": False}
    monkeypatch.setattr(demo, "demonstrate", lambda output: report)
    monkeypatch.setattr(sys, "argv", [demo.__file__, "--output", str(tmp_path / "new")])
    assert demo.main() == 1
    captured = capsys.readouterr()
    assert captured.out == json.dumps(report, indent=2, sort_keys=True) + "\n"
    assert captured.err == ""

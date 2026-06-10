"""End-to-end OIM test: quiet install + uninstall against a synthetic archive.

Builds a minimal project tree with one OIM entry, zips it as the installer's
fallback ``binaries.zip``, runs ``Installer.py --Quiet`` and then
``Uninstaller.py --Quiet`` as subprocesses, and asserts the staging / script-
exec / log-record / cleanup / uninstall-hook behavior.  No SolidWorks or real
release build required.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
STRUCT = HERE.parent / "VIStk" / "Structures"


def _build_project(p: Path):
    """Write a minimal valid project tree under *p*."""
    vis = p / "runtime" / ".VIS"
    vis.mkdir(parents=True)
    project = {
        "TestApp": {
            "Screens": {},
            "defaults": {"icon": "x", "default_screen": None},
            "metadata": {"version": "1.0.0", "company": "testco"},
            "release_info": {"location": "./dist/", "hidden_imports": [], "groups": {}},
            "host": {"script": ".VIS/Host.py"},
        }
    }
    (vis / "project.json").write_text(json.dumps(project), encoding="utf-8")

    # An OIM entry: manifest (default-on), media payload, install + uninstall.
    oim = p / "OIM" / "TestMedia"
    (oim / "media").mkdir(parents=True)
    (oim / "script").mkdir(parents=True)
    (oim / "icon").mkdir(parents=True)
    (oim / "manifest.json").write_text(
        json.dumps({"label": "Test Media", "description": "demo", "default": True}),
        encoding="utf-8",
    )
    (oim / "media" / "payload.txt").write_text("PAYLOAD", encoding="utf-8")
    (oim / "icon" / "icon.txt").write_text("not-a-real-image", encoding="utf-8")
    # install.py: prove context is injected, media is staged, and write a marker.
    (oim / "script" / "install.py").write_text(
        "import os\n"
        "assert OIM_NAME == 'TestMedia', OIM_NAME\n"
        "assert APP_TITLE == 'TestApp', APP_TITLE\n"
        "assert os.path.isdir(RUNTIME_DIR), RUNTIME_DIR\n"
        "payload = os.path.join(MEDIA_DIR, 'payload.txt')\n"
        "assert open(payload).read() == 'PAYLOAD'\n"
        "open(os.path.join(INSTALL_ROOT, 'INSTALL_RAN.marker'), 'w').write(OIM_NAME)\n"
        "log('install marker written')\n",
        encoding="utf-8",
    )
    # uninstall.py: write a marker OUTSIDE the install root (the parent dir),
    # since the uninstaller's blind sweep wipes everything under INSTALL_ROOT
    # right after this hook runs — a real hook also acts outside the dir
    # (unregister COM, etc.).
    (oim / "script" / "uninstall.py").write_text(
        "import os\n"
        "parent = os.path.dirname(INSTALL_ROOT)\n"
        "open(os.path.join(parent, 'UNINSTALL_RAN.marker'), 'w').write(OIM_NAME)\n"
        "log('uninstall marker written')\n",
        encoding="utf-8",
    )


def _zip_dir(src: Path, zip_path: Path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in src.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(src).as_posix())


def main():
    tmp = Path(tempfile.mkdtemp(prefix="oim_e2e_"))
    try:
        proj = tmp / "proj"
        proj.mkdir()
        _build_project(proj)

        # Stage Installer.py + Uninstaller.py in a dir with binaries.zip beside.
        run_dir = tmp / "run"
        run_dir.mkdir()
        shutil.copy2(STRUCT / "Installer.py", run_dir / "Installer.py")
        shutil.copy2(STRUCT / "Uninstaller.py", run_dir / "Uninstaller.py")
        _zip_dir(proj, run_dir / "binaries.zip")

        install_target = tmp / "target"  # installer appends /TestApp
        install_root = install_target / "TestApp"

        env = dict(os.environ)
        # Ensure the editable VIStk import resolves for the subprocess.
        env["PYTHONPATH"] = str(STRUCT.parent.parent) + os.pathsep + env.get("PYTHONPATH", "")

        # -- Install --------------------------------------------------------
        r = subprocess.run(
            [sys.executable, str(run_dir / "Installer.py"),
             "--Quiet", "--Path", str(install_target)],
            capture_output=True, text=True, env=env, cwd=str(run_dir),
        )
        print("-- installer stdout --\n" + r.stdout)
        if r.returncode != 0:
            print("-- installer stderr --\n" + r.stderr)
            raise SystemExit(f"installer exited {r.returncode}")

        log_path = install_root / "runtime" / ".VIS" / "install_log.json"
        assert log_path.exists(), f"missing install log at {log_path}"
        log = json.loads(log_path.read_text())
        assert "oim" in log, "install_log has no 'oim' array"
        names = [r["name"] for r in log["oim"]]
        assert names == ["TestMedia"], names
        rec = log["oim"][0]
        assert rec["uninstall_script"] == "runtime/.VIS/oim/TestMedia/uninstall.py", rec

        assert (install_root / "INSTALL_RAN.marker").exists(), "install.py did not run"
        assert not (install_root / "OIM").exists(), "staged OIM/ was not cleaned up"
        assert (install_root / "runtime" / ".VIS" / "oim" / "TestMedia" / "uninstall.py").exists(), \
            "uninstall script was not persisted"
        print("PASS install: oim recorded, script ran, staging cleaned, uninstall persisted")

        # -- Uninstall ------------------------------------------------------
        # --Path is the install ROOT; _find_install_log() reads
        # <root>/runtime/.VIS/install_log.json and OIM paths resolve via the
        # log's recorded install_location.
        ru = subprocess.run(
            [sys.executable, str(run_dir / "Uninstaller.py"),
             "--Quiet", "--Path", str(install_root)],
            capture_output=True, text=True, env=env, cwd=str(run_dir),
        )
        print("-- uninstaller stdout --\n" + ru.stdout)
        if ru.returncode != 0:
            print("-- uninstaller stderr --\n" + ru.stderr)
            raise SystemExit(f"uninstaller exited {ru.returncode}")

        assert (install_target / "UNINSTALL_RAN.marker").exists(), "uninstall.py did not run"
        print("PASS uninstall: uninstall hook ran")

        print("\nALL OIM E2E CHECKS PASSED")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()

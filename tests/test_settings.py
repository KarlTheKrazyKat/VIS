"""Smoke + unit tests for VIStk.Structures._Settings.ProjectSettings.

Run: python tests/test_settings.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from VIStk.Structures._Settings import ProjectSettings


class _FakeProject:
    """Minimal stand-in: ProjectSettings only needs ``p_settings``."""
    def __init__(self, vinfo_dir):
        self.p_settings = os.path.join(vinfo_dir, "settings.json")


_failures = []


def check(label, cond):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        _failures.append(label)


def main():
    with tempfile.TemporaryDirectory() as d:
        vinfo = os.path.join(d, ".VIS")
        os.makedirs(vinfo)
        proj = _FakeProject(vinfo)

        print("missing-file / defaults:")
        s = ProjectSettings(proj)
        check("missing file -> DEFAULTS value", s.get("notifications.duration_ms") == 5000)
        check("missing file -> no settings.json written on read",
              not os.path.exists(proj.p_settings))
        check("unknown key -> None", s.get("nope.nope") is None)
        check("explicit default wins over DEFAULTS",
              s.get("notifications.duration_ms", 1234) == 1234)
        check("explicit default for unknown key",
              s.get("nope.nope", "x") == "x")

        print("set / save / reload:")
        s.set("notifications.duration_ms", 3000)
        s.set("appearance.font_family", "Consolas")
        check("set then get (in memory)", s.get("notifications.duration_ms") == 3000)
        check("save() returns True", s.save() is True)
        check("settings.json now exists", os.path.exists(proj.p_settings))

        # Overrides-only: file must NOT contain untouched DEFAULTS keys.
        with open(proj.p_settings) as f:
            raw = json.load(f)
        check("file holds only overrides", set(raw.keys()) ==
              {"notifications.duration_ms", "appearance.font_family"})

        s2 = ProjectSettings(proj)
        check("reload sees saved override", s2.get("notifications.duration_ms") == 3000)
        check("reload: untouched key still DEFAULT",
              s2.get("notifications.enabled") is True)

        print("effective / reset / contains:")
        eff = s2.effective()
        check("effective() merges DEFAULTS + overrides",
              eff["appearance.font_family"] == "Consolas"
              and eff["host.start_with_os"] is False
              and len(eff) == len(ProjectSettings.DEFAULTS))
        check("__contains__ true for override", "appearance.font_family" in s2)
        check("__contains__ false for default-only", "host.start_with_os" not in s2)
        s2.reset("appearance.font_family")
        check("reset() drops override -> back to default",
              s2.get("appearance.font_family") is None)

        print("corrupt-file tolerance:")
        with open(proj.p_settings, "w") as f:
            f.write("{ this is not json ]")
        s3 = ProjectSettings(proj)
        check("corrupt file -> falls back to defaults (no crash)",
              s3.get("notifications.duration_ms") == 5000)

        print("non-object json tolerance:")
        with open(proj.p_settings, "w") as f:
            json.dump([1, 2, 3], f)
        s4 = ProjectSettings(proj)
        check("array json -> ignored, defaults used",
              s4.get("notifications.enabled") is True)

        print("dirty flag (conditional save-on-close):")
        s5 = ProjectSettings(proj)
        check("fresh load -> not dirty", s5.dirty is False)
        s5.set("notifications.duration_ms", 7000)
        check("set changed value -> dirty", s5.dirty is True)
        s5.save()
        check("save -> clears dirty", s5.dirty is False)
        s5.set("notifications.duration_ms", 7000)
        check("set same value -> still not dirty", s5.dirty is False)
        s5.reset("notifications.duration_ms")
        check("reset present override -> dirty", s5.dirty is True)
        s5.save()
        s5.reset("not.present")
        check("reset absent key -> not dirty", s5.dirty is False)

        print("mutable-default safety:")
        check("host.last_tabs default is None (not a shared list)",
              ProjectSettings.DEFAULTS["host.last_tabs"] is None)
        check("all DEFAULTS values immutable",
              all(v is None or isinstance(v, (bool, int, str))
                  for v in ProjectSettings.DEFAULTS.values()))

    print()
    if _failures:
        print(f"{len(_failures)} FAILED: {_failures}")
        sys.exit(1)
    print("ALL PASSED")


if __name__ == "__main__":
    main()

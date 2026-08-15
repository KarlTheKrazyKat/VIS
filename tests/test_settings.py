"""Smoke + unit tests for VIStk.Structures._Settings.ProjectSettings.

Run: python tests/test_settings.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from VIStk.Structures._Settings import ProjectSettings, SCHEMA_VERSION


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

        # Full-file: save writes the complete resolved set (defaults +
        # overrides) so the file stays whole and hand-editable.
        with open(proj.p_settings) as f:
            raw = json.load(f)
        check("file holds the full default set",
              set(raw.keys()) == set(ProjectSettings.DEFAULTS.keys()))
        check("file reflects overridden values",
              raw["notifications.duration_ms"] == 3000
              and raw["appearance.font_family"] == "Consolas")
        check("file keeps untouched keys at default",
              raw["notifications.enabled"] is True)

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

    # ensure_file() materializes a default file in a fresh dir.
    with tempfile.TemporaryDirectory() as d2:
        vinfo2 = os.path.join(d2, ".VIS")
        os.makedirs(vinfo2)
        proj2 = _FakeProject(vinfo2)

        print("ensure_file (default-file materialization):")
        sf = ProjectSettings(proj2)
        check("no file before ensure_file", not os.path.exists(proj2.p_settings))
        check("ensure_file() writes a file (returns True)", sf.ensure_file() is True)
        check("file now exists", os.path.exists(proj2.p_settings))
        check("ensure_file does not mark dirty", sf.dirty is False)
        with open(proj2.p_settings) as f:
            seeded = json.load(f)
        check("materialized file holds the full default set",
              seeded == ProjectSettings.DEFAULTS)
        check("ensure_file is idempotent (no rewrite when present)",
              sf.ensure_file() is False)

        # ensure_file must not clobber an existing (user-edited) file.
        sf.set("notifications.duration_ms", 1234)
        sf.save()
        sf2 = ProjectSettings(proj2)
        check("ensure_file leaves an existing file untouched",
              sf2.ensure_file() is False
              and sf2.get("notifications.duration_ms") == 1234)

    # v0 -> v1 migration: 0.6.0-0.6.4 wrote appearance.color_scheme="system"
    # into every generated file while the setting did nothing.  In 0.6.5 that
    # value means "follow the OS", so an unstamped one must not read as a pick.
    with tempfile.TemporaryDirectory() as d3:
        vinfo3 = os.path.join(d3, ".VIS")
        os.makedirs(vinfo3)
        proj3 = _FakeProject(vinfo3)

        print("schema migration (v0 -> v1):")
        with open(proj3.p_settings, "w") as f:
            json.dump({"appearance.color_scheme": "system",
                       "window.min_width": 400}, f)
        legacy = ProjectSettings(proj3)
        check("legacy 'system' is not treated as a pick",
              "appearance.color_scheme" not in legacy)
        check("unrelated override survives migration",
              legacy.get("window.min_width") == 400)
        check("migration marks dirty so the stamp gets written",
              legacy.dirty is True)
        legacy.save()
        with open(proj3.p_settings) as f:
            check("save stamps the schema version",
                  json.load(f)["settings.version"] == SCHEMA_VERSION)

        with open(proj3.p_settings, "w") as f:
            json.dump({"settings.version": SCHEMA_VERSION,
                       "appearance.color_scheme": "system"}, f)
        chosen = ProjectSettings(proj3)
        check("a 'system' pick in a stamped file is kept",
              "appearance.color_scheme" in chosen)
        check("a stamped file does not re-migrate", chosen.dirty is False)

    print()
    if _failures:
        print(f"{len(_failures)} FAILED: {_failures}")
        sys.exit(1)
    print("ALL PASSED")


if __name__ == "__main__":
    main()

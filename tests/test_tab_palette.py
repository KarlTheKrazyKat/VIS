"""Logic tests for tab-strip palette derivation.

Covers the shading helpers, the roles derived from a recoloured strip
background, and the two entry points that use them — ``Styles.resolve`` for a
style whose overrides repaint the bar, and ``TabBar.setPalette(bar=...)`` for
an app recolouring the shipped look.  Needs no Tk display.

Run: python tests/test_tab_palette.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_failures = []


def check(label, cond):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}")
    if not cond:
        _failures.append(label)


def luma(color):
    from VIStk.Styles._palette import _rgb
    r, g, b = _rgb(color)
    return 0.299 * r + 0.587 * g + 0.114 * b


def run_shading():
    from VIStk.Styles import dim, lift
    from VIStk.Styles._palette import _rgb

    print("shading:")
    check("parses #rrggbb", _rgb("#2b4f7a") == (43, 79, 122))
    check("parses #rgb", _rgb("#abc") == (170, 187, 204))
    check("parses greyNN without a Tk root", _rgb("grey62") == (158, 158, 158))
    check("parses grayNN spelling", _rgb("gray25") == _rgb("grey25"))
    check("unresolvable colour is None", _rgb("NotAColour") is None)

    check("dim darkens", luma(dim("#808080", 0.2)) < luma("#808080"))
    check("lift lightens", luma(lift("#808080", 0.2)) > luma("#808080"))
    check("dim flips on near-black", luma(dim("#000000", 0.2)) > 0)
    check("lift flips on near-white", luma(lift("#ffffff", 0.2)) < luma("#ffffff"))
    check("unresolvable colour passes through", dim("NotAColour", 0.2) == "NotAColour")


def run_companions():
    from VIStk.Styles import bar_companions

    print("bar_companions:")
    light = bar_companions("#f7f8fa")
    check("focused matches the bar", light["focused"] == "#f7f8fa")
    check("empty stays near a light bar", luma(light["empty"]) > 200)
    check("empty is dimmer than the bar", luma(light["empty"]) < luma("#f7f8fa"))
    check("unfocused is dimmer than empty", luma(light["unfocused"]) < luma(light["empty"]))

    dark = bar_companions("#2b2b2b")
    check("empty stays near a dark bar", luma(dark["empty"]) < 60)
    check("drag highlight lifts off a dark bar",
          luma(dark["empty_hover"]) > luma("#2b2b2b"))

    kept = bar_companions("#f7f8fa", skip={"empty", "unfocused"})
    check("skipped roles are omitted", set(kept) == {"focused", "empty_hover"})


def run_resolve():
    from VIStk.Styles import LIGHT, DARK, TabStyle, register, resolve

    print("resolve:")
    check("classic on light is the untouched scheme", resolve("light", "classic").palette == LIGHT)
    check("classic on dark is the untouched scheme", resolve("dark", "classic").palette == DARK)
    check("a style that leaves bar_bg alone keeps the scheme empty",
          resolve("light", "underline").palette.empty == LIGHT.empty)

    register("t_corporate", TabStyle.from_preset("underline", palette={"bar_bg": "#2b2b2b"}))
    pal = resolve("light", "t_corporate").palette
    check("overriding bar_bg carries focused", pal.focused == "#2b2b2b")
    check("overriding bar_bg carries empty", luma(pal.empty) < 60)
    check("overriding bar_bg carries unfocused", luma(pal.unfocused) < luma("#2b2b2b"))

    register("t_explicit", TabStyle.from_preset(
        "classic", palette={"bar_bg": "#2b2b2b", "empty": "#ff0000"}))
    check("an explicit empty override wins",
          resolve("light", "t_explicit").palette.empty == "#ff0000")


def run_set_palette():
    from VIStk.Widgets import TabBar

    print("setPalette:")
    TabBar.setStyle("classic")
    TabBar.setPalette(bar="#f7f8fa", selected="#ffffff", text="#20242b")
    pal = TabBar._active_style.palette
    check("bar recolours the strip", pal.bar_bg == "#f7f8fa" and pal.focused == "#f7f8fa")
    check("empty bar follows the new bar colour", luma(pal.empty) > 200)
    check("unfocused pane follows the new bar colour", luma(pal.unfocused) > 150)

    TabBar.setStyle("pill")
    check("derived roles are sticky across a style switch",
          TabBar._active_style.palette.empty == pal.empty)

    TabBar.setPalette(bar="#1d1f23")
    check("recolouring again re-derives", luma(TabBar._active_style.palette.empty) < 60)


def run_registry():
    # The app-facing spelling: palettes are registered and curated on Project,
    # as classmethods, so styles.py needs no project.json parse.
    from VIStk.Structures._Project import Project
    from VIStk.Styles import Palette, resolve_palette, set_default_palette

    print("registry (Project):")
    check("ships light and dark", {"light", "dark"} <= set(Project.paletteNames()))
    check("lookup is case-insensitive",
          Project.getPalette("LIGHT") is Project.getPalette("light"))
    check("unknown name is None", Project.getPalette("nope") is None)

    Project.registerPalette("t_brand", Palette.from_preset("light", bar_bg="#f7f8fa"))
    Project.registerPalette("t_brand_dark", Palette.from_preset("dark", bar_bg="#1d1f23"))
    check("registering adds one slot", Project.paletteNames().count("t_brand") == 1)
    Project.registerPalette("t_brand", Palette.from_preset("light", bar_bg="#eeeeee"))
    check("re-registering keeps its slot", Project.paletteNames().count("t_brand") == 1)

    Project.offerPalettes(["t_brand", "t_brand_dark", "light"], default="t_brand")
    check("offered list is what was curated",
          Project.offeredPalettes() == ["t_brand", "t_brand_dark", "light"])
    check("offerPalettes sets the default", Project.defaultPalette() == "t_brand")
    check("offerPalettes paints the default too (no Host needed)",
          Project.activePalette().bar_bg == Project.getPalette("t_brand").bar_bg)
    check("an unknown default is rejected",
          _raises(lambda: set_default_palette("not_registered"), ValueError))

    check("an unknown pick falls back to the default",
          resolve_palette("gone") is Project.getPalette("t_brand"))
    Project.setSystemPalettes("t_brand", "t_brand_dark")
    from VIStk.Styles import os_scheme
    expected = "t_brand_dark" if os_scheme() == "dark" else "t_brand"
    check("system resolves to the app's pair",
          resolve_palette("system") is Project.getPalette(expected))
    check("os_scheme answers light or dark", os_scheme() in ("light", "dark"))

    # The namespace is open: any name an app invents is a colour, and names it
    # doesn't define fall through to the base palette.
    check("an app's own name is just a colour",
          Palette.from_preset("light", whatever_we_call_it="#fff")
          .whatever_we_call_it == "#fff")
    check("undefined names fall through to the base",
          Palette.from_preset("dark", bar_bg="#111").surface
          == Project.getPalette("dark").surface)
    check("an undefined name resolves to None, not an error",
          Palette.from_preset("light").get("never_defined") is None)


def run_precedence():
    from VIStk.Structures._Project import Project
    from VIStk.Widgets import TabBar
    from VIStk.Styles import Palette

    print("precedence:")
    Project.offerPalettes(["t_brand", "t_brand_dark", "light"], default="t_brand")
    Project.setDefaultPalette("t_brand")
    check("app default paints the bars",
          Project.activePalette() is Project.getPalette("t_brand"))

    Project.setActivePalette("t_brand_dark")          # the user's pick
    check("a user pick overrides the app default",
          Project.activePalette() is Project.getPalette("t_brand_dark"))
    TabBar.setStyle("underline")
    check("the pick survives a style switch",
          Project.activePalette().bar_bg == Project.getPalette("t_brand_dark").bar_bg)
    Project.setActivePalette(None)
    # Compared by role, not identity: a style with overrides (underline, still
    # active here) resolves to a derived copy of the registered palette.
    check("clearing the pick returns to the app default",
          Project.activePalette().bar_bg == Project.getPalette("t_brand").bar_bg)

    Project.setDefaultPalette(Palette.from_preset("dark", bar_bg="#101214"),
                              name="t_inline")
    check("setDefaultPalette registers an inline palette",
          Project.activePalette().bar_bg == "#101214")
    check("TabBar and Project agree on the active palette",
          TabBar.activePalette() is Project.activePalette())


def _raises(fn, exc) -> bool:
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False


if __name__ == "__main__":
    run_shading()
    run_companions()
    run_resolve()
    run_registry()
    run_precedence()
    run_set_palette()
    print()
    if _failures:
        print(f"{len(_failures)} failed: " + ", ".join(_failures))
        sys.exit(1)
    print("all passed")

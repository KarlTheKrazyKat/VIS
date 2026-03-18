from __future__ import annotations

from tkinter import Toplevel

from VIStk.Objects._TabManager import TabManager
from VIStk.Widgets._HostMenu import HostMenu
from VIStk.Widgets._InfoRow import InfoRow


class DetachedWindow:
    """A floating window containing its own ``TabManager``, ``HostMenu``,
    and ``InfoRow``.

    Created by the ``Host`` when a tab is popped out (right-click "Open in
    new window") or drag-detached (released outside all tab bars).  The
    window is tracked in ``host._detached``.

    The window is created as a peer ``Toplevel`` (not parented to the Host)
    so all application windows are at the same level.

    When all tabs are removed (e.g. dragged elsewhere), the window stays
    open and shows an empty drop-zone strip — it does not close itself.
    Only the user's X button or a ``Host.quit_host()`` call closes it.

    Window title follows the same ``"project: screen — info"`` format as
    the main Host window.
    """

    def __init__(self, host, name: str, module, hooks, icon, base_name: str,
                 x_root: int = 0, y_root: int = 0,
                 btn_offset_x: int = 0, btn_offset_y: int = 0):
        """
        Args:
            host:         The owning ``Host`` instance.
            name:         Display name of the first screen tab.
            module:       Imported screen module for *name*.
            hooks:        Optional hooks module for *name*.
            icon:         Optional ``PIL.ImageTk.PhotoImage`` for the tab icon.
            base_name:    Screen registry name used to re-import the screen.
            x_root:       Screen x coordinate of the cursor at detach time.
            y_root:       Screen y coordinate of the cursor at detach time.
            btn_offset_x: Cursor x offset within the original tab button.
            btn_offset_y: Cursor y offset within the original tab button.
        """
        self.host = host
        self._closing = False

        # Peer window — not parented to Host so all windows are at same level.
        # Withdraw immediately so we can position before the user ever sees it.
        self.win = Toplevel()
        self.win.withdraw()
        self.win.title(name)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        # ── Menu bar ──────────────────────────────────────────────────────────
        self.HostMenu = HostMenu(self.win, close_command=self._on_close)
        self.HostMenu.attach()

        # ── Tab content area ──────────────────────────────────────────────────
        self.tab_manager = TabManager(self.win)
        self.tab_manager.pack(fill="both", expand=True)

        # ── Status bar ────────────────────────────────────────────────────────
        self.InfoRow = InfoRow(self.win, host.Project)
        self.InfoRow.pack(fill="x", side="bottom")

        # Register for FPS updates from the Host tick loop
        host._fps_listeners.append(self.InfoRow.set_fps)

        # Wire lifecycle callbacks
        self.tab_manager.on_tab_activate    = self._on_tab_activate
        self.tab_manager.on_tab_deactivate  = self._on_tab_deactivate
        self.tab_manager.on_tab_popout      = self._on_tab_popout
        self.tab_manager.on_tab_detach      = self._on_tab_detach
        self.tab_manager.on_tab_refresh     = self._on_tab_refresh
        self.tab_manager.on_tab_info_change = self._on_tab_info_change

        # Set window icon
        self._load_icon()

        # Open the first tab
        self.tab_manager.open_tab(name, module, hooks=hooks, icon=icon,
                                  base_name=base_name)

        # Position the window so the cursor lands on the tab at the same offset
        self._position_window(x_root, y_root, btn_offset_x, btn_offset_y)

    # ── Positioning ────────────────────────────────────────────────────────────

    def _position_window(self, x_root: int, y_root: int,
                         btn_offset_x: int, btn_offset_y: int):
        """Position the window so the cursor sits over the new tab at the same offset."""
        import re

        try:
            host_w = self.host.winfo_width()
            host_h = self.host.winfo_height()
        except Exception:
            host_w, host_h = 800, 600

        # Anchor at origin so widget layout is computed at a known position.
        # The window is already withdrawn so there is no visible flash.
        self.win.geometry(f"{host_w}x{host_h}+0+0")
        self.win.update_idletasks()

        try:
            tab_names = list(self.tab_manager._tabs.keys())
            if tab_names:
                btn = self.tab_manager.tab_bar._tabs[tab_names[0]]["button"]

                # Walk the widget tree using winfo_x/y() (position relative to
                # parent, layout-computed by the geometry manager).  These are
                # reliable even for withdrawn windows; winfo_rootx/y() is NOT
                # because it depends on the WM having actually mapped the window.
                btn_in_win_x, btn_in_win_y = 0, 0
                w = btn
                while True:
                    btn_in_win_x += w.winfo_x()
                    btn_in_win_y += w.winfo_y()
                    p = w.winfo_parent()
                    if not p or p == str(self.win):
                        break
                    w = w.nametowidget(p)

                # Decoration height = OS title bar + native Tk menu bar.
                # geometry("+x+y") encodes the outer-frame origin; winfo_rooty()
                # returns the client-area y.  Parse the Host geometry string
                # (Host is always mapped so the string is accurate) and compare
                # it to winfo_rooty() to get the true offset.  If the platform
                # uses client-area coords in geometry strings the result is 0,
                # which is also correct for that convention.
                m = re.search(r'([+-]\d+)([+-]\d+)$', self.host.geometry())
                host_geo_y = int(m.group(2)) if m else self.host.winfo_rooty()
                deco_h = max(0, self.host.winfo_rooty() - host_geo_y)

                # Position the outer frame so cursor lands at btn_offset within button.
                win_x = x_root - btn_offset_x - btn_in_win_x
                win_y = y_root - btn_offset_y - btn_in_win_y - deco_h

                self.win.geometry(f"+{win_x}+{win_y}")
        except Exception:
            pass

        self.win.deiconify()

    def _load_icon(self):
        try:
            import glob as _glob
            import PIL.Image
            import PIL.ImageTk
            matches = _glob.glob(
                self.host.Project.p_icons + "/" + self.host.Project.d_icon + ".*"
            )
            if matches:
                img = PIL.Image.open(matches[0]).convert("RGBA").resize((32, 32))
                self.win.iconphoto(True, PIL.ImageTk.PhotoImage(img))
        except Exception:
            pass

    # ── Lifecycle callbacks ────────────────────────────────────────────────────

    def _on_tab_activate(self, name: str, module):
        """Update title, InfoRow, and menu when a tab gains focus."""
        info = self.tab_manager._tabs.get(name, {}).get("info", "")
        self._set_title(name, info)
        base_name = self.tab_manager._tabs.get(name, {}).get("base_name", name)
        scr = self.host.Project.getScreen(base_name)
        self.InfoRow.set_screen(name, str(scr.s_version) if scr else "")
        # configure_menu: hooks module first, then screen module
        hooks = self.tab_manager._tabs.get(name, {}).get("hooks")
        cfg = (getattr(hooks, "configure_menu", None)
               or getattr(module, "configure_menu", None))
        if cfg:
            try:
                cfg(self.HostMenu)
            except Exception:
                pass

    def _on_tab_deactivate(self, name: str | None):
        self.HostMenu.clear_screen_items()
        if name is None:
            # All tabs removed — show empty state but don't close
            self.win.title(self.host.Project.title)
            self.InfoRow.set_screen("")

    def _on_tab_info_change(self, name: str, info: str):
        if self.tab_manager.active == name:
            self._set_title(name, info)

    def _set_title(self, screen: str, info: str = ""):
        base = self.host.Project.title
        if info:
            self.win.title(f"{base}: {screen} \u2014 {info}")
        else:
            self.win.title(f"{base}: {screen}")

    def _on_tab_popout(self, name: str):
        """Send tab back to the main Host."""
        if not self.tab_manager.has_tab(name):
            return
        entry     = self.tab_manager._tabs[name]
        base_name = entry.get("base_name", name)
        icon      = entry.get("icon")
        self.tab_manager.close_tab(name)
        scr = self.host.Project.getScreen(base_name)
        if scr:
            module2 = self.host._import_screen(scr)
            hooks2  = self.host._import_hooks(scr)
            icon2   = self.host._load_tab_icon(scr)
        else:
            module2 = entry.get("module")
            hooks2  = entry.get("hooks")
            icon2   = icon
        display = self.host._unique_display_name(name)
        self.host.TabManager.open_tab(display, module2, hooks=hooks2, icon=icon2,
                                      base_name=base_name)
        self.host.deiconify()

    def _on_tab_detach(self, name: str):
        """Drag out of this window — send to main Host at cursor position."""
        if not self.tab_manager.has_tab(name):
            return
        entry     = self.tab_manager._tabs[name]
        base_name = entry.get("base_name", name)
        module    = entry.get("module")
        hooks     = entry.get("hooks")
        icon      = entry.get("icon")
        bx = self.tab_manager.tab_bar._last_drag_btn_offset_x
        by = self.tab_manager.tab_bar._last_drag_btn_offset_y
        self.tab_manager.close_tab(name)
        x = self.host.winfo_pointerx()
        y = self.host.winfo_pointery()
        dw = DetachedWindow(
            self.host, name, module, hooks, icon, base_name,
            x, y, bx, by,
        )
        self.host._detached.append(dw)

    def _on_tab_refresh(self, name: str):
        if not self.tab_manager.has_tab(name):
            return
        entry     = self.tab_manager._tabs[name]
        base_name = entry.get("base_name", name)
        icon      = entry.get("icon")
        idx       = self.tab_manager.tab_bar.get_tab_idx(name)
        scr = self.host.Project.getScreen(base_name)
        if scr is None:
            self.tab_manager.force_refresh_tab(name)
            return
        self.tab_manager.close_tab(name)
        module = self.host._import_screen(scr)
        hooks  = self.host._import_hooks(scr)
        self.tab_manager.open_tab(name, module, hooks=hooks, icon=icon,
                                  insert_idx=idx, base_name=base_name)

    def _on_close(self):
        """Close all tabs and remove from Host tracking."""
        if self._closing:
            return
        self._closing = True
        for name in list(self.tab_manager._tabs.keys()):
            self.tab_manager.close_tab(name)
        # Deregister FPS listener
        try:
            self.host._fps_listeners.remove(self.InfoRow.set_fps)
        except (ValueError, AttributeError):
            pass
        try:
            self.win.destroy()
        except Exception:
            pass
        try:
            self.host._detached.remove(self)
        except ValueError:
            pass

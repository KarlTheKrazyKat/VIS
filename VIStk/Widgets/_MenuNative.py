"""Native Windows menubar patching (bitmaps + right-justify) via ctypes/user32.

Tk renders the menubar as a real Win32 menu (an ``HMENU`` on the wrapper
window), but exposes none of the native item styling — no per-item bitmap on
the bar and no right-alignment.  This module patches the ``HMENU`` Tk built,
*after* Tk builds it, using ``SetMenuItemInfoW``:

* ``pil_to_hbitmap`` converts a PIL image to a 32bpp **premultiplied-alpha**
  top-down DIB section (PARGB), which the themed menu alpha-blends cleanly.
* ``patch`` sets ``hbmpItem`` (``MIIM_BITMAP``) and/or ORs
  ``MFT_RIGHTJUSTIFY`` into ``fType`` (``MIIM_FTYPE``) on one bar item by
  position, then ``DrawMenuBar``.  ``MFT_RIGHTJUSTIFY`` right-aligns that
  item **and all subsequent items**.

Everything no-ops gracefully off-Windows: ``available()`` is ``False``,
``patch`` returns ``False``, ``pil_to_hbitmap`` returns ``None`` and
``menu_height()`` falls back to 20, so callers never need a platform guard.

Ground truth (verified by spike on Windows 11 x64, Python 3.13, Tk 8.6):

* The HWND that owns the menu is the Tk *wrapper* window —
  ``int(window.wm_frame(), 16)`` — NOT ``winfo_id()``.
* restypes/argtypes MUST be set (``wintypes.HMENU`` etc.) or 64-bit handles
  truncate.  ``sizeof(MENUITEMINFOW)`` is 80 on x64.
* Bitmaps render on the bar with clean alpha blending (no black halo);
  text + bitmap both render on the same bar item.
* ``MFT_RIGHTJUSTIFY`` works and is confirmed in ``fType`` readback
  (0x4000); it also right-aligns every item after the patched one.
* Tk menus here are all ``tearoff=0``, so Tk entry index *i* == native menu
  position *i* (``GetMenuItemCount`` matched the Tk count, strings in
  order).
* ``WM_COMMAND`` with the item's ``wID`` dispatches to the Tk callback, so
  a patched entry stays clickable through Tk's normal plumbing.
* **Tk REBUILDS the item info whenever the Tk menu is mutated** (add /
  delete / entryconfigure): the ``HMENU`` handle survives but ``hbmpItem``
  and ``fType`` are reset to 0 — out-of-band patches are dropped and must
  be re-applied (``HostMenu`` hooks every mutating method for this).
* ``SM_CYMENU`` was 20 on the spike machine.
* One ``CreateDIBSection`` handle came back sign-extended to 64 bits —
  compare handles only through a consistent restype path (this module's
  ``pil_to_hbitmap`` / ``current_hbitmap`` both go through
  ``wintypes.HBITMAP``).
"""

import sys

_WIN = sys.platform == "win32"

if _WIN:
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.windll.user32
    _gdi32 = ctypes.windll.gdi32

    # ── Win32 constants ────────────────────────────────────────────────────────
    MIIM_ID = 0x2
    MIIM_BITMAP = 0x80
    MIIM_FTYPE = 0x100
    MFT_RIGHTJUSTIFY = 0x4000
    SM_CYMENU = 15

    # ── Structures (x64 layout — cbSize/sizeof = 80) ───────────────────────────
    class MENUITEMINFOW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.UINT),
            ("fMask", wintypes.UINT),
            ("fType", wintypes.UINT),
            ("fState", wintypes.UINT),
            ("wID", wintypes.UINT),
            ("hSubMenu", wintypes.HMENU),
            ("hbmpChecked", wintypes.HBITMAP),
            ("hbmpUnchecked", wintypes.HBITMAP),
            ("dwItemData", ctypes.c_size_t),
            ("dwTypeData", wintypes.LPWSTR),
            ("cch", wintypes.UINT),
            ("hbmpItem", wintypes.HBITMAP),
        ]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD),
            ("biWidth", ctypes.c_long),
            ("biHeight", ctypes.c_long),
            ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD),
            ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD),
            ("biXPelsPerMeter", ctypes.c_long),
            ("biYPelsPerMeter", ctypes.c_long),
            ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [
            ("bmiHeader", BITMAPINFOHEADER),
            ("bmiColors", wintypes.DWORD * 3),
        ]

    # ── Prototypes — 64-bit handles truncate without these ─────────────────────
    _user32.GetMenu.restype = wintypes.HMENU
    _user32.GetMenu.argtypes = [wintypes.HWND]
    _user32.GetMenuItemInfoW.restype = wintypes.BOOL
    _user32.GetMenuItemInfoW.argtypes = [
        wintypes.HMENU, wintypes.UINT, wintypes.BOOL,
        ctypes.POINTER(MENUITEMINFOW)]
    _user32.SetMenuItemInfoW.restype = wintypes.BOOL
    _user32.SetMenuItemInfoW.argtypes = [
        wintypes.HMENU, wintypes.UINT, wintypes.BOOL,
        ctypes.POINTER(MENUITEMINFOW)]
    _user32.DrawMenuBar.restype = wintypes.BOOL
    _user32.DrawMenuBar.argtypes = [wintypes.HWND]
    _user32.GetSystemMetrics.restype = ctypes.c_int
    _user32.GetSystemMetrics.argtypes = [ctypes.c_int]
    _user32.GetDC.restype = wintypes.HDC
    _user32.GetDC.argtypes = [wintypes.HWND]
    _user32.ReleaseDC.restype = ctypes.c_int
    _user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    _gdi32.CreateDIBSection.restype = wintypes.HBITMAP
    _gdi32.CreateDIBSection.argtypes = [
        wintypes.HDC, ctypes.POINTER(BITMAPINFO), wintypes.UINT,
        ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD]
    _gdi32.DeleteObject.restype = wintypes.BOOL
    _gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]


def available() -> bool:
    """Whether native menubar patching is available (Windows only)."""
    return _WIN


def menu_height() -> int:
    """Height of the native menu bar in pixels (``SM_CYMENU``).

    Returns:
        The system menu-bar height, or ``20`` off-Windows / on failure.
    """
    if not _WIN:
        return 20
    try:
        h = _user32.GetSystemMetrics(SM_CYMENU)
        return h if h > 0 else 20
    except Exception:
        return 20


def pil_to_hbitmap(pil_image):
    """Convert a PIL image to an ``HBITMAP`` the themed menu can alpha-blend.

    Builds a 32bpp **premultiplied-alpha** top-down DIB section (PARGB) —
    plain RGBA renders with black halos on the themed menu bar; each channel
    must be multiplied by alpha first.

    Args:
        pil_image: A ``PIL.Image.Image`` (any mode — converted to RGBA).

    Returns:
        The ``HBITMAP`` handle as an ``int``, or ``None`` off-Windows / on
        failure.  The caller owns the handle — free it with
        :func:`delete_hbitmap` when the menu no longer references it.
    """
    if not _WIN:
        return None
    try:
        from PIL import Image, ImageChops
        img = pil_image.convert("RGBA")
        r, g, b, a = img.split()
        r = ImageChops.multiply(r, a)
        g = ImageChops.multiply(g, a)
        b = ImageChops.multiply(b, a)
        pre = Image.merge("RGBA", (r, g, b, a))
        bits = pre.tobytes("raw", "BGRA")

        w, h = img.size
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h      # negative = top-down
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0  # BI_RGB

        hdc = _user32.GetDC(0)
        pbits = ctypes.c_void_p()
        try:
            hbmp = _gdi32.CreateDIBSection(
                hdc, ctypes.byref(bmi), 0, ctypes.byref(pbits), None, 0)
        finally:
            _user32.ReleaseDC(0, hdc)
        if not hbmp or not pbits.value:
            return None
        ctypes.memmove(pbits, bits, len(bits))
        return int(hbmp)
    except Exception:
        return None


def delete_hbitmap(handle) -> None:
    """Free an ``HBITMAP`` returned by :func:`pil_to_hbitmap`.

    Safe to call with ``None`` / ``0`` or off-Windows (no-op).

    Args:
        handle: The bitmap handle to free.
    """
    if not _WIN or not handle:
        return
    try:
        _gdi32.DeleteObject(handle)
    except Exception:
        pass


def _get_hmenu(window):
    """Return ``(hwnd, hmenu)`` for *window*'s wrapper frame, or ``(0, 0)``.

    The menu lives on the Tk *wrapper* window (``wm_frame``), not the widget
    HWND from ``winfo_id()``.
    """
    try:
        hwnd = int(window.wm_frame(), 16)
    except Exception:
        return 0, 0
    if not hwnd:
        return 0, 0
    hmenu = _user32.GetMenu(hwnd)
    return hwnd, (hmenu or 0)


def patch(window, position, hbitmap=None, right=False) -> bool:
    """Patch one native menubar item in place.

    Reads the item's current ``fType`` first (read-modify-write, so other
    type flags survive), then applies ``MIIM_BITMAP`` and/or
    ``MIIM_FTYPE`` | ``MFT_RIGHTJUSTIFY`` with ``SetMenuItemInfoW`` and calls
    ``DrawMenuBar``.  Note ``MFT_RIGHTJUSTIFY`` right-aligns the item **and
    every item after it**.

    Args:
        window:   The ``Tk`` / ``Toplevel`` whose menubar to patch.
        position: Native item position — equal to the Tk entry index because
                  every VIStk menu is ``tearoff=0``.
        hbitmap:  Optional ``HBITMAP`` (from :func:`pil_to_hbitmap`) to show
                  on the item.  The menu does not take ownership — keep the
                  handle alive while the item shows it.
        right:    OR ``MFT_RIGHTJUSTIFY`` into the item's ``fType``.

    Returns:
        ``True`` on success, ``False`` off-Windows or on any failure
        (including a window with no native menu — ``GetMenu`` returns 0).
    """
    if not _WIN:
        return False
    try:
        hwnd, hmenu = _get_hmenu(window)
        if not hmenu:
            return False

        mii = MENUITEMINFOW()
        mii.cbSize = ctypes.sizeof(MENUITEMINFOW)
        fmask = 0
        if right:
            # Read-modify-write fType so we only add the justify flag.
            mii.fMask = MIIM_FTYPE
            if not _user32.GetMenuItemInfoW(hmenu, position, True,
                                            ctypes.byref(mii)):
                return False
            mii.fType |= MFT_RIGHTJUSTIFY
            fmask |= MIIM_FTYPE
        if hbitmap:
            mii.hbmpItem = hbitmap
            fmask |= MIIM_BITMAP
        if not fmask:
            return True  # nothing requested — trivially done

        mii.fMask = fmask
        if not _user32.SetMenuItemInfoW(hmenu, position, True,
                                        ctypes.byref(mii)):
            return False
        _user32.DrawMenuBar(hwnd)
        return True
    except Exception:
        return False


def current_hbitmap(window, position):
    """Read back the ``hbmpItem`` currently set on a native menubar item.

    Cheap verification that an earlier :func:`patch` survived — Tk resets
    ``hbmpItem`` (and ``fType``) whenever the Tk menu is mutated, so a
    mismatch means the patch was dropped and must be re-applied.

    Args:
        window:   The ``Tk`` / ``Toplevel`` whose menubar to read.
        position: Native item position (== Tk entry index).

    Returns:
        The ``HBITMAP`` handle as an ``int``, or ``None`` when no bitmap is
        set / off-Windows / on failure.
    """
    if not _WIN:
        return None
    try:
        _hwnd, hmenu = _get_hmenu(window)
        if not hmenu:
            return None
        mii = MENUITEMINFOW()
        mii.cbSize = ctypes.sizeof(MENUITEMINFOW)
        mii.fMask = MIIM_BITMAP
        if not _user32.GetMenuItemInfoW(hmenu, position, True,
                                        ctypes.byref(mii)):
            return None
        return int(mii.hbmpItem) if mii.hbmpItem else None
    except Exception:
        return None

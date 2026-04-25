"""Documentation-URL helpers (0.5.0).

A project author wires a Help button in one line from ``.VIS/Host.py``::

    from VIStk.Widgets import HostMenu
    from VIStk.Objects import open_active_screen_docs

    host_menu.add_project_command("Help", open_active_screen_docs)

At click time :func:`open_active_screen_docs` reads the currently active
screen from the Host, consults ``Project.resolve_docs_url`` (active
screen's ``docs`` -> project ``default_docs`` -> ``None``), and hands the
URL to :func:`webbrowser.open`.

The URL is passed through verbatim — no path normalisation.  Authors
write fully-qualified URLs (``https://...``, ``file:///...``) in
``project.json``.
"""

import webbrowser


def open_active_screen_docs() -> bool:
    """Open the active screen's docs URL (or the project default) in the
    system's default web browser.

    Returns:
        ``True`` when a URL was resolved and handed to ``webbrowser.open``,
        ``False`` when no URL is configured for the active screen or as a
        project default (or no screen is active).  Callers may surface a
        status-line notice on ``False`` if they want to; this helper is
        silent either way.
    """
    from VIStk.Structures._Project import Project
    url = Project().resolve_docs_url()
    if not url:
        return False
    try:
        webbrowser.open(url)
    except Exception:
        return False
    return True

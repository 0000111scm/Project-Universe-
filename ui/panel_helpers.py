"""Small safe helpers used by the side panel.

Full draw_panel extraction is intentionally postponed: the current main.py still owns many
runtime globals. These helpers are the first safe cut to avoid UI index crashes.
"""

def get_catalog_item_safe(catalog, selection):
    if selection is None:
        return None
    try:
        tab_i, body_i = selection
        tabs = list(catalog.values())
        if tab_i < 0 or tab_i >= len(tabs):
            return None
        bodies = tabs[tab_i]
        if body_i < 0 or body_i >= len(bodies):
            return None
        return bodies[body_i]
    except Exception:
        return None

def compact_body_label(body, max_len=22):
    name = getattr(body, "name", "") or "Corpo"
    if len(name) <= max_len:
        return name
    return name[:max_len-1] + "…"


def should_draw_body_label(body, selected_body=None, followed_body=None, zoom=1.0):
    if body is selected_body or body is followed_body:
        return True
    if getattr(body, "is_fragment", False):
        return getattr(body, "label_timer", 0.0) > 0.0 and zoom >= 1.4
    if not getattr(body, "show_label", True):
        return False
    if getattr(body, "mass", 0) < 10 and zoom < 1.2:
        return False
    return zoom >= 0.18

"""Small, non-destructive migration of the integration-owned Lovelace view title.

Never overwrite an unrelated/custom dashboard. Updates only the old
integration-generated, single-panel layout whose heading is still Time of Use.
"""
from copy import deepcopy

OLD_VIEW_TITLE = "Time of Use"
NEW_VIEW_TITLE = "SAJ H2 Control"
DASHBOARD_TITLE = "SAJ TOU Control"
CARD_TYPE = "custom:saj-tou-dynamic-card"


def migrate_generated_view_title(config):
    """Return updated config or None when no safe legacy match is present."""
    if not isinstance(config, dict):
        return None
    if config.get("title") != DASHBOARD_TITLE:
        return None
    views = config.get("views")
    if not isinstance(views, list) or len(views) != 1:
        return None
    view = views[0]
    if not isinstance(view, dict):
        return None
    if (
        view.get("title") != OLD_VIEW_TITLE
        or view.get("path") != "tou"
        or view.get("type") != "panel"
        or view.get("cards") != [{"type": CARD_TYPE}]
    ):
        return None
    updated = deepcopy(config)
    updated["views"][0]["title"] = NEW_VIEW_TITLE
    return updated

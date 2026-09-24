import greentechhub_ui
from fastapi import Response
from greentechhub_fastapi import htmx

CLOSE_MODAL = "closeModal"


def hx_response(message: str, kind: str = "success", *, title: str | None = None,
                events: tuple[str, ...] = ()) -> Response:
    """Bodyless 204 whose only job is its HX-Trigger header: a gth toast plus
    any extra events (CLOSE_MODAL, a table's refresh event)."""
    return htmx.hx_response(greentechhub_ui.toast(message, kind, title=title, events=events))

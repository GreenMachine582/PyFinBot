import greentechhub_ui
from fastapi import Response, status

CLOSE_MODAL = "closeModal"


def hx_response(message: str, kind: str = "success", *, events: tuple[str, ...] = ()) -> Response:
    """Bodyless 204 whose only job is its HX-Trigger header: a gth toast plus
    any extra events (CLOSE_MODAL, a table's refresh event)."""
    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
        headers={"HX-Trigger": greentechhub_ui.toast(message, kind, events=events)},
    )

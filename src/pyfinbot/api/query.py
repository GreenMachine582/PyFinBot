"""The API list routes' query: greentechhub-fastapi's PageParams (page, size,
sort, filter, filters) as a core PageRequest, which the routes hand to
greentechhub_core.sqlalchemy.query.page with their allow-list.

PageParams.to_page_request() would answer bad input with a 422; PyFinBot's
API has always answered it with a 400 "invalid_filters" (and now
"invalid_sort"), so this parses with the same functions and keeps that.
"""

from greentechhub_core.query.types import PageRequest
from greentechhub_core.types import BadRequestError
from greentechhub_fastapi.query import PageParams
from greentechhub_fastapi.query.parsing import parse_filter_json, parse_filters, parse_sort


def page_request(params: PageParams) -> PageRequest:
    """`sort`: "field,-other". `filters`: JSON {"field", "op", "value"}
    clauses and {"and": [...]} / {"or": [...]} groups; `filter`: the flat
    "field:op:value,..." form. Unknown fields are ignored by the allow-list."""
    try:
        sort = parse_sort(params.sort)
    except ValueError as exc:
        raise BadRequestError(f"Invalid 'sort': {exc}", code="invalid_sort") from exc
    try:
        filters = [*parse_filters(params.filter), *parse_filter_json(params.filters)]
    except ValueError as exc:
        raise BadRequestError(f"Invalid 'filters': {exc}", code="invalid_filters") from exc
    return PageRequest(page=params.page, size=params.size, sort=sort, filters=filters)

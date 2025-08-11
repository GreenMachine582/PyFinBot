
from __future__ import annotations

import json
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Union

from sqlalchemy.orm.attributes import InstrumentedAttribute

# A "sortable" can be a column/attribute or a function that returns one
Sortable = Union[InstrumentedAttribute, Any]
SortableFactory = Callable[[Any], Sortable]  # receives model class


def _resolveSortable(model: Any, thing: Union[str, Sortable, SortableFactory]) -> Optional[Sortable]:
    """
    - str: attribute name on model
    - Sortable: as is
    - SortableFactory: call with model
    """
    if callable(thing) and not isinstance(thing, InstrumentedAttribute):
        return thing(model)
    if isinstance(thing, str):
        return getattr(model, thing, None)
    return thing


def _buildSortOrderBy(
    *,
    model: Any,
    sort: Optional[str],
    allowed: Optional[Mapping[str, Union[str, Sortable, SortableFactory]]] = None,
    default: Optional[Sequence[Union[str, Sortable, SortableFactory]]] = None,
) -> List[Any]:
    """
    Parse a sort string like 'market,-symbol' into a SQLAlchemy order_by list.

    Args:
      model: SQLModel/SQLAlchemy model class (e.g., Stock)
      sort: comma-separated fields, '-' prefix for desc. e.g. "market,-symbol"
      allowed: map of allowed public keys -> column/attr or name or factory.
               If None, will auto-allow model.__table__.columns by their names.
      default: sequence used when sort is falsy or every token is invalid.
               Can be strings/attrs/factories.

    Returns:
      list suitable for Select.order_by(*list)
    """
    # Build an allowlist mapping: public -> actual sortable
    if allowed is None:
        # Auto-allow direct table columns by name
        # (sa_column.key matches attribute name for SQLModel)
        allowed = {c.key: getattr(model, c.key, None) for c in model.__table__.columns}  # type: ignore[attr-defined]

    order_by: List[Any] = []

    tokens: Iterable[str] = []
    if sort:
        tokens = (t.strip() for t in sort.split(","))
    else:
        tokens = []

    for token in tokens:
        if not token:
            continue
        desc = token.startswith("-")
        key = token[1:] if desc else token
        col = _resolveSortable(model, allowed.get(key))
        if col is None:
            continue
        order_by.append(col.desc() if desc else col.asc())

    # Fallback to defaults
    if not order_by:
        if default:
            for item in default:
                col = _resolveSortable(model, item)
                if col is not None:
                    # default always ascending; pass a lambda for custom desc if needed
                    order_by.append(col.asc())
        else:
            # If no defaults provided, try model primary key asc as a sane default
            # (works for SQLModel/SA 2.0 if PK is named "id")
            pk = getattr(model, "id", None)
            if pk is not None:
                order_by.append(pk.asc())

    return order_by


def buildSortOrderBy(model, allowed,  sorters_json: Optional[str], fallback_sort: Optional[str]) -> list:
    """
    Prefer Tabulator sorters (JSON list of {field,dir}), else fallback to 'sort' string.
    """
    if sorters_json:
        try:
            sorters: List[Dict[str, Any]] = json.loads(sorters_json)
        except json.JSONDecodeError:
            sorters = []
        if sorters:
            parts = []
            for s in sorters:
                field = str(s.get("field", "")).strip()
                dir_ = s.get("dir", "asc")
                if not field:
                    continue
                parts.append(("-" + field) if dir_ == "desc" else field)
            joined = ",".join(parts)
            return _buildSortOrderBy(model=model, sort=joined, allowed=allowed)

    # fallback to plain sort string (e.g. "market,-symbol")
    return _buildSortOrderBy(model=model, sort=fallback_sort, allowed=allowed)

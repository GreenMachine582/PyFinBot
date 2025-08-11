from __future__ import annotations
from typing import Any, Dict, List, Mapping, Optional, Union

from sqlalchemy import and_, or_, not_, literal
from sqlalchemy.orm.attributes import InstrumentedAttribute

# Public ops supported (common subset of sqlalchemy-filters)
# '==' '!=' '>' '>=' '<' '<=' 'like' 'ilike' 'not_like' 'not_ilike'
# 'in' 'not_in' 'is_null' 'is_not_null'
# Also accept 'contains' (string icontains convenience)

Op = str

def _getCol(model: Any, field: str) -> Optional[InstrumentedAttribute]:
    return getattr(model, field, None)

def _opToExpr(col: InstrumentedAttribute, op: Op, value: Any):
    # Normalize op aliases
    op = op.lower()
    if op in ("==", "eq", "equal"):
        return col == value
    if op in ("!=", "<>", "ne", "not_equal"):
        return col != value
    if op in (">", "gt"):
        return col > value
    if op in (">=", "gte", "greater_or_equal"):
        return col >= value
    if op in ("<", "lt"):
        return col < value
    if op in ("<=", "lte", "less_or_equal"):
        return col <= value
    if op in ("like",):
        return col.like(value)
    if op in ("not_like",):
        return ~col.like(value)
    if op in ("ilike",):
        return col.ilike(value)
    if op in ("not_ilike",):
        return ~col.ilike(value)
    if op in ("contains", "icontains"):
        return col.ilike(f"%{value}%")
    if op in ("in",):
        vals = value if isinstance(value, (list, tuple, set)) else [value]
        return col.in_(list(vals))
    if op in ("not_in", "nin"):
        vals = value if isinstance(value, (list, tuple, set)) else [value]
        return ~col.in_(list(vals))
    if op in ("is_null", "isnull"):
        return col.is_(None)
    if op in ("is_not_null", "notnull", "isnotnull"):
        return col.is_not(None)

    # Unknown op -> return a harmless TRUE so it doesn't break the tree
    return literal(True)

def buildWhereFromSAFSpec(
    *,
    model: Any,
    spec: Union[Dict[str, Any], List[Dict[str, Any]], None],
    allowed_fields: Optional[Mapping[str, str]] = None,
):
    """
    Convert a 'sqlalchemy-filters' style spec into a SQLAlchemy boolean expression.

    spec can be:
      - list of rules/groups
      - dict with 'and'/'or' keys
      - leaf dict: {'field': 'name', 'op': 'ilike', 'value': '%acme%'}
      - group dict: {'and': [...]} or {'or': [...]}
      - negation: {'not': {...}}

    allowed_fields: optional map of external field -> actual model attribute name.
                    If None, uses the spec 'field' as attribute name.
    """
    if not spec:
        return None

    def _resolveField(field: str) -> Optional[str]:
        if allowed_fields is None:
            return field
        return allowed_fields.get(field)

    def _parseNode(node: Union[Dict[str, Any], List[Dict[str, Any]]]):
        # List means implicit AND (matches common usage)
        if isinstance(node, list):
            parts = [_parseNode(n) for n in node if n]
            parts = [p for p in parts if p is not None]
            if not parts:
                return None
            expr = parts[0]
            for p in parts[1:]:
                expr = and_(expr, p)
            return expr

        if "and" in node:
            items = node["and"] or []
            parts = [_parseNode(n) for n in items]
            parts = [p for p in parts if p is not None]
            if not parts:
                return None
            expr = parts[0]
            for p in parts[1:]:
                expr = and_(expr, p)
            return expr

        if "or" in node:
            items = node["or"] or []
            parts = [_parseNode(n) for n in items]
            parts = [p for p in parts if p is not None]
            if not parts:
                return None
            expr = parts[0]
            for p in parts[1:]:
                expr = or_(expr, p)
            return expr

        if "not" in node:
            inner = _parseNode(node["not"])
            return not_(inner) if inner is not None else None

        # Leaf rule
        field = node.get("field")
        op = node.get("op")
        value = node.get("value", None)

        if not field or not op:
            return None

        field_name = _resolveField(field)
        if not field_name:
            return None

        col = _getCol(model, field_name)
        if col is None:
            return None

        return _opToExpr(col, op, value)

    return _parseNode(spec)

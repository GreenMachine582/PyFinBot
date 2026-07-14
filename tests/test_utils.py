"""Unit tests for sorting and filter helper utilities."""
import json

import pytest
from sqlmodel import select

from pyfinbot.core.sorting import buildSortOrderBy
from pyfinbot.core.sa_filters_compat import buildWhereFromSAFSpec
from pyfinbot.models.stock_models import Stock


ALLOWED = {
    "id": "id",
    "symbol": "symbol",
    "market": "market",
    "name": "name",
    "is_active": "is_active",
}


class TestBuildSortOrderBy:
    def test_single_ascending_field(self):
        result = buildSortOrderBy(Stock, ALLOWED, None, "symbol")
        assert len(result) == 1
        # Should produce symbol ASC
        assert "symbol" in str(result[0])

    def test_single_descending_field(self):
        result = buildSortOrderBy(Stock, ALLOWED, None, "-symbol")
        assert len(result) == 1
        assert "DESC" in str(result[0]).upper()

    def test_multiple_fields(self):
        result = buildSortOrderBy(Stock, ALLOWED, None, "market,-symbol")
        assert len(result) == 2

    def test_unknown_field_is_ignored(self):
        result = buildSortOrderBy(Stock, ALLOWED, None, "nonexistent,symbol")
        assert len(result) == 1  # only symbol survives

    def test_tabulator_sorters_takes_priority(self):
        sorters = json.dumps([{"field": "name", "dir": "asc"}])
        result = buildSortOrderBy(Stock, ALLOWED, sorters, "symbol")
        assert len(result) == 1
        assert "name" in str(result[0])

    def test_tabulator_desc_sorter(self):
        sorters = json.dumps([{"field": "symbol", "dir": "desc"}])
        result = buildSortOrderBy(Stock, ALLOWED, sorters, None)
        assert "DESC" in str(result[0]).upper()

    def test_empty_sort_falls_back_to_pk(self):
        result = buildSortOrderBy(Stock, ALLOWED, None, None)
        assert len(result) == 1  # fallback to PK (id)


class TestBuildWhereFromSAFSpec:
    def test_eq_leaf_rule(self):
        spec = {"field": "market", "op": "==", "value": "ASX"}
        expr = buildWhereFromSAFSpec(model=Stock, spec=spec, allowed_fields=ALLOWED)
        assert expr is not None

    def test_ilike_leaf_rule(self):
        spec = {"field": "name", "op": "ilike", "value": "%group%"}
        expr = buildWhereFromSAFSpec(model=Stock, spec=spec, allowed_fields=ALLOWED)
        assert expr is not None

    def test_and_group(self):
        spec = {"and": [
            {"field": "market", "op": "==", "value": "ASX"},
            {"field": "is_active", "op": "==", "value": True},
        ]}
        expr = buildWhereFromSAFSpec(model=Stock, spec=spec, allowed_fields=ALLOWED)
        assert expr is not None

    def test_or_group(self):
        spec = {"or": [
            {"field": "market", "op": "==", "value": "ASX"},
            {"field": "market", "op": "==", "value": "NASDAQ"},
        ]}
        expr = buildWhereFromSAFSpec(model=Stock, spec=spec, allowed_fields=ALLOWED)
        assert expr is not None

    def test_list_is_implicit_and(self):
        spec = [
            {"field": "market", "op": "==", "value": "ASX"},
            {"field": "is_active", "op": "==", "value": True},
        ]
        expr = buildWhereFromSAFSpec(model=Stock, spec=spec, allowed_fields=ALLOWED)
        assert expr is not None

    def test_unknown_field_returns_none(self):
        spec = {"field": "nonexistent", "op": "==", "value": "x"}
        expr = buildWhereFromSAFSpec(model=Stock, spec=spec, allowed_fields=ALLOWED)
        assert expr is None

    def test_empty_spec_returns_none(self):
        expr = buildWhereFromSAFSpec(model=Stock, spec=None, allowed_fields=ALLOWED)
        assert expr is None

    def test_not_negation(self):
        spec = {"not": {"field": "market", "op": "==", "value": "ASX"}}
        expr = buildWhereFromSAFSpec(model=Stock, spec=spec, allowed_fields=ALLOWED)
        assert expr is not None

    def test_in_operator(self):
        spec = {"field": "market", "op": "in", "value": ["ASX", "NASDAQ"]}
        expr = buildWhereFromSAFSpec(model=Stock, spec=spec, allowed_fields=ALLOWED)
        assert expr is not None

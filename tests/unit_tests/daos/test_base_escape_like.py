# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""Tests for _escape_like and column-operator safety in BaseDAO."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

from superset.daos.base import (
    BaseDAO,
    ColumnOperator,
    ColumnOperatorEnum,
    _escape_like,
)

_TestBase = declarative_base()


class _TestModel(_TestBase):  # type: ignore[misc, valid-type]
    __tablename__ = "_escape_like_test"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)


class _TestDAO(BaseDAO[_TestModel]):
    model_cls = _TestModel


# ---------------------------------------------------------------------------
# _escape_like — string safety
# ---------------------------------------------------------------------------


def test_escape_like_normal_string() -> None:
    assert _escape_like("hello") == "hello"


def test_escape_like_percent() -> None:
    assert _escape_like("hello%world") == r"hello\%world"


def test_escape_like_underscore() -> None:
    assert _escape_like("hello_world") == r"hello\_world"


def test_escape_like_backslash() -> None:
    assert _escape_like(r"hello\world") == r"hello\\world"


def test_escape_like_empty_string() -> None:
    assert _escape_like("") == ""


# ---------------------------------------------------------------------------
# _escape_like — non-string values (should not crash)
# ---------------------------------------------------------------------------


def test_escape_like_int() -> None:
    result = _escape_like(42)
    assert isinstance(result, str)
    assert result == "42"


def test_escape_like_float() -> None:
    result = _escape_like(3.14)
    assert isinstance(result, str)


def test_escape_like_list() -> None:
    result = _escape_like([1, 2, 3])
    assert isinstance(result, str)


def test_escape_like_dict() -> None:
    result = _escape_like({"key": "value"})
    assert isinstance(result, str)


def test_escape_like_none() -> None:
    result = _escape_like(None)
    assert isinstance(result, str)
    assert result == "None"


def test_escape_like_bool() -> None:
    result = _escape_like(True)
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# apply_column_operators — empty/null values
# ---------------------------------------------------------------------------


def test_apply_column_operators_empty_string_value() -> None:
    """An empty-string filter is applied as-is by the operator layer
    (the guard that strips empty filters lives in the calling code, not
    inside apply_column_operators)."""
    op = ColumnOperator(col="name", opr="ct", value="")
    # Should not crash — _escape_like coerces empty string safely
    with patch.object(_TestDAO, "model_cls", _TestModel):
        query = MagicMock()
        query.filter.return_value = query
        _TestDAO.apply_column_operators(query, [op])
        query.filter.assert_called_once()


def test_apply_column_operators_non_string_value() -> None:
    """A non-string filter value should not crash the operator layer."""
    op = ColumnOperator(col="name", opr="ct", value=12345)
    with patch.object(_TestDAO, "model_cls", _TestModel):
        query = MagicMock()
        query.filter.return_value = query
        _TestDAO.apply_column_operators(query, [op])
        query.filter.assert_called_once()


def test_apply_column_operators_object_value() -> None:
    """An object (dict) filter value should not crash — _escape_like
    coerces it to string."""
    op = ColumnOperator(col="name", opr="ct", value={"nested": "obj"})
    with patch.object(_TestDAO, "model_cls", _TestModel):
        query = MagicMock()
        query.filter.return_value = query
        _TestDAO.apply_column_operators(query, [op])
        query.filter.assert_called_once()

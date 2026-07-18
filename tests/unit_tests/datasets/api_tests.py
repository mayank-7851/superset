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

from typing import Any
from unittest.mock import MagicMock, patch

from sqlalchemy.orm.session import Session

from superset import db


def test_put_invalid_dataset(
    session: Session,
    client: Any,
    full_api_access: None,
) -> None:
    """
    Test invalid payloads.
    """
    from superset.connectors.sqla.models import SqlaTable
    from superset.models.core import Database

    SqlaTable.metadata.create_all(db.session.get_bind())

    database = Database(
        database_name="my_db",
        sqlalchemy_uri="sqlite://",
    )
    dataset = SqlaTable(
        table_name="test_put_invalid_dataset",
        database=database,
    )
    db.session.add(dataset)
    db.session.flush()

    response = client.put(
        "/api/v1/dataset/1",
        json={"invalid": "payload"},
    )
    assert response.status_code == 422
    assert response.json == {
        "errors": [
            {
                "message": "The schema of the submitted payload is invalid.",
                "error_type": "MARSHMALLOW_ERROR",
                "level": "error",
                "extra": {
                    "messages": {"invalid": ["Unknown field."]},
                    "payload": {"invalid": "payload"},
                    "issue_codes": [
                        {
                            "code": 1040,
                            "message": (
                                "Issue 1040 - The submitted payload failed validation."
                            ),
                        }
                    ],
                },
            }
        ]
    }


def test_get_dataset_include_rendered_sql_passes_table_to_template_processor(
    session: Session,
    client: Any,
    full_api_access: None,
) -> None:
    """
    Dataset API: Test that include_rendered_sql passes the table
    to get_template_processor.

    Regression test for the bug where get_template_processor was called without
    the `table` argument, leaving self._schema as None in processors like
    PrestoTemplateProcessor and causing NPEs when templates reference partition
    functions without an explicit schema.
    """
    from superset.connectors.sqla.models import SqlaTable
    from superset.models.core import Database

    SqlaTable.metadata.create_all(db.session.get_bind())

    database = Database(
        database_name="my_db",
        sqlalchemy_uri="sqlite://",
    )
    dataset = SqlaTable(
        table_name="test_render_sql_table",
        schema="my_schema",
        database=database,
        sql="SELECT 1",
    )
    db.session.add(dataset)
    db.session.flush()

    mock_processor = MagicMock()
    mock_processor.process_template.return_value = "SELECT 1"

    with patch(
        "superset.datasets.api.get_template_processor",
        return_value=mock_processor,
    ) as mock_get_processor:
        response = client.get(
            f"/api/v1/dataset/{dataset.id}?include_rendered_sql=true",
        )

    assert response.status_code == 200
    mock_get_processor.assert_called_once_with(database=database, table=dataset)


def test_handle_filters_args_returns_request_scoped_filters(
    session: Session,
    client: Any,
    full_api_access: None,
) -> None:
    """
    ``_handle_filters_args`` must return a fresh ``Filters`` instance per
    call so concurrent requests don't share filter state.

    Regression test for #33828: under concurrent traffic the FAB default
    implementation mutates ``self._filters`` (a single shared instance),
    causing filters from one request to leak into another.

    The fix lives on ``BaseSupersetModelRestApi`` so every superset REST
    API subclass (datasets, charts, dashboards, saved queries, etc.)
    inherits the request-scoped behavior. This test exercises it via
    ``DatasetRestApi`` as a concrete subclass.
    """
    from flask_appbuilder.const import API_FILTERS_RIS_KEY

    from superset.datasets.api import DatasetRestApi

    api = DatasetRestApi()
    api.datamodel = MagicMock()
    api.search_columns = ["table_name"]
    api.search_filters = {}
    api._base_filters = MagicMock()  # noqa: SLF001

    # Each call should construct a fresh Filters instance via datamodel.get_filters
    rison_args = {
        API_FILTERS_RIS_KEY: [{"col": "table_name", "opr": "eq", "value": "a"}],
    }
    api._handle_filters_args(rison_args)  # noqa: SLF001
    api._handle_filters_args(rison_args)  # noqa: SLF001

    assert api.datamodel.get_filters.call_count == 2
    # Returned object must be the joined-filters result of the *fresh* Filters,
    # not the shared self._filters attribute.
    fresh_filters = api.datamodel.get_filters.return_value
    assert fresh_filters.rest_add_filters.call_count == 2
    assert fresh_filters.get_joined_filters.call_count == 2


def test_handle_filters_args_strips_empty_values(
    session: Session,
    client: Any,
    full_api_access: None,
) -> None:
    """Filters with empty / null / whitespace-only values must be
    stripped from the rison args so they don't match every row
    (issue #33)."""
    from flask_appbuilder.const import API_FILTERS_RIS_KEY

    from superset.datasets.api import DatasetRestApi

    api = DatasetRestApi()
    api.datamodel = MagicMock()
    api.search_columns = ["table_name"]
    api.search_filters = {}
    api._base_filters = MagicMock()  # noqa: SLF001

    # — empty string value is stripped —
    rison_args: dict[str, Any] = {
        API_FILTERS_RIS_KEY: [
            {"col": "table_name", "opr": "ct", "value": ""},
        ],
    }
    api._handle_filters_args(rison_args)  # noqa: SLF001
    fresh_filters = api.datamodel.get_filters.return_value
    # rest_add_filters should receive an empty list
    call_args = fresh_filters.rest_add_filters.call_args[0][0]
    assert call_args == []

    # — whitespace-only value is stripped —
    api.datamodel.reset_mock()
    rison_args = {
        API_FILTERS_RIS_KEY: [
            {"col": "table_name", "opr": "ct", "value": "   "},
        ],
    }
    api._handle_filters_args(rison_args)  # noqa: SLF001
    fresh_filters = api.datamodel.get_filters.return_value
    call_args = fresh_filters.rest_add_filters.call_args[0][0]
    assert call_args == []

    # — None value is stripped —
    api.datamodel.reset_mock()
    rison_args = {
        API_FILTERS_RIS_KEY: [
            {"col": "table_name", "opr": "eq", "value": None},
        ],
    }
    api._handle_filters_args(rison_args)  # noqa: SLF001
    fresh_filters = api.datamodel.get_filters.return_value
    call_args = fresh_filters.rest_add_filters.call_args[0][0]
    assert call_args == []

    # — valid value (including "0") passes through —
    api.datamodel.reset_mock()
    rison_args = {
        API_FILTERS_RIS_KEY: [
            {"col": "table_name", "opr": "ct", "value": "foo"},
            {"col": "id", "opr": "eq", "value": 0},
        ],
    }
    api._handle_filters_args(rison_args)  # noqa: SLF001
    fresh_filters = api.datamodel.get_filters.return_value
    call_args = fresh_filters.rest_add_filters.call_args[0][0]
    assert len(call_args) == 2
    assert call_args[0]["value"] == "foo"
    assert call_args[1]["value"] == 0

    # — mixed: only empty is stripped —
    api.datamodel.reset_mock()
    rison_args = {
        API_FILTERS_RIS_KEY: [
            {"col": "table_name", "opr": "ct", "value": ""},
            {"col": "table_name", "opr": "ct", "value": "foo"},
        ],
    }
    api._handle_filters_args(rison_args)  # noqa: SLF001
    fresh_filters = api.datamodel.get_filters.return_value
    call_args = fresh_filters.rest_add_filters.call_args[0][0]
    assert len(call_args) == 1
    assert call_args[0]["value"] == "foo"

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
import numpy as np
import pandas as pd

from superset.utils.pandas_postprocessing import rank
from tests.unit_tests.pandas_postprocessing.utils import round_floats, series_to_list


def test_rank_no_group_by():
    """Rank percentile across entire dataset without grouping."""
    df = pd.DataFrame(
        {
            "region": ["West", "West", "West"],
            "product": ["A", "B", "C"],
            "sales": [100.0, 200.0, 150.0],
        }
    )
    result = rank(df.copy(), metric="sales")
    assert "rank" in result.columns
    assert len(result) == 3
    ranks = round_floats(series_to_list(result["rank"]), 4)
    assert ranks == [round(1 / 3, 4), 1.0, round(2 / 3, 4)]


def test_rank_with_group_by_multiple_groups():
    """Rank percentile grouped by region with multiple regions."""
    df = pd.DataFrame(
        {
            "region": ["West", "West", "East", "East"],
            "product": ["A", "B", "A", "B"],
            "sales": [100.0, 200.0, 150.0, 300.0],
        }
    )
    result = rank(df.copy(), metric="sales", group_by="region")
    assert "rank" in result.columns
    assert len(result) == 4
    # Within each group of 2, ranks should be 0.5 and 1.0
    ranks = round_floats(series_to_list(result["rank"]), 4)
    # West: 100 -> 0.5, 200 -> 1.0; East: 150 -> 0.5, 300 -> 1.0
    assert set(ranks) == {0.5, 1.0}


def test_rank_single_group_with_group_by():
    """Rank percentile when filtered to a single region (the bug case).

    When all data belongs to a single group, ``DataFrame.groupby().apply()``
    returns a DataFrame instead of a Series, which causes ``df["rank"] = ...``
    to raise ``ValueError: Cannot set a DataFrame with multiple columns to the
    single column rank``.  The fix uses ``.transform()`` which always returns
    a Series aligned with the original index.
    """
    df = pd.DataFrame(
        {
            "region": ["West", "West", "West"],
            "product": ["A", "B", "C"],
            "sales": [100.0, 200.0, 150.0],
        }
    )
    result = rank(df.copy(), metric="sales", group_by="region")
    assert "rank" in result.columns
    assert len(result) == 3
    ranks = round_floats(series_to_list(result["rank"]), 4)
    assert ranks == [round(1 / 3, 4), 1.0, round(2 / 3, 4)]


def test_rank_single_row_with_group_by():
    """Rank percentile with a single row and group_by (1x1 heatmap edge case)."""
    df = pd.DataFrame(
        {
            "region": ["West"],
            "product": ["A"],
            "sales": [100.0],
        }
    )
    result = rank(df.copy(), metric="sales", group_by="region")
    assert "rank" in result.columns
    assert len(result) == 1
    assert result["rank"].iloc[0] == 1.0


def test_rank_single_row_no_group_by():
    """Rank percentile with a single row and no group_by."""
    df = pd.DataFrame(
        {
            "region": ["West"],
            "product": ["A"],
            "sales": [100.0],
        }
    )
    result = rank(df.copy(), metric="sales")
    assert "rank" in result.columns
    assert len(result) == 1
    assert result["rank"].iloc[0] == 1.0


def test_rank_preserves_original_columns():
    """Rank should add a rank column without removing existing columns."""
    df = pd.DataFrame(
        {
            "region": ["West", "East"],
            "product": ["A", "B"],
            "sales": [100.0, 200.0],
        }
    )
    result = rank(df.copy(), metric="sales")
    assert list(result.columns) == ["region", "product", "sales", "rank"]


def test_rank_same_metric_values():
    """Rank percentile with identical metric values should produce same rank."""
    df = pd.DataFrame(
        {
            "region": ["West", "West", "West"],
            "product": ["A", "B", "C"],
            "sales": [100.0, 100.0, 100.0],
        }
    )
    result = rank(df.copy(), metric="sales")
    assert "rank" in result.columns
    assert len(result) == 3
    # All values identical -> pandas rank(pct=True) uses average method:
    # each gets the average percentile (1+2+3)/3 / 3 = 2/3 ≈ 0.6667
    for rank_val in result["rank"]:
        assert np.isclose(rank_val, 2 / 3)


def test_rank_with_nan_values():
    """Rank percentile with NaN metric values should handle gracefully."""
    df = pd.DataFrame(
        {
            "region": ["West", "West", "West"],
            "product": ["A", "B", "C"],
            "sales": [100.0, np.nan, 150.0],
        }
    )
    result = rank(df.copy(), metric="sales", group_by="region")
    assert "rank" in result.columns
    assert len(result) == 3
    # NaN values should not cause a crash; rank for NaN row is NaN
    assert np.isnan(result.loc[1, "rank"])


def test_rank_with_group_by_different_column_types():
    """Rank percentile with group_by on columns with different value types."""
    df = pd.DataFrame(
        {
            "region": [1, 1, 2, 2],
            "product": ["A", "B", "A", "B"],
            "sales": [100.0, 200.0, 150.0, 300.0],
        }
    )
    result = rank(df.copy(), metric="sales", group_by="region")
    assert "rank" in result.columns
    assert len(result) == 4


def test_rank_two_rows_per_group_with_group_by():
    """Rank percentile: two rows per group should work correctly."""
    df = pd.DataFrame(
        {
            "region": ["West", "West"],
            "product": ["A", "B"],
            "sales": [100.0, 200.0],
        }
    )
    result = rank(df.copy(), metric="sales", group_by="region")
    assert "rank" in result.columns
    ranks = round_floats(series_to_list(result["rank"]), 4)
    assert ranks == [0.5, 1.0]

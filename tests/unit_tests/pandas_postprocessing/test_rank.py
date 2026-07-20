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
import pandas as pd

from superset.utils.pandas_postprocessing import rank


def test_rank_no_group():
    """Rank without group_by should compute percentile rank across all rows."""
    df = pd.DataFrame({"value": [10, 20, 30, 40, 50]})
    result = rank(df, metric="value")
    assert "rank" in result.columns
    expected = [0.2, 0.4, 0.6, 0.8, 1.0]
    for i, exp in enumerate(expected):
        assert abs(result["rank"].iloc[i] - exp) < 0.001


def test_rank_with_group_multiple_groups():
    """Rank with group_by should compute percentile rank within each group."""
    df = pd.DataFrame(
        {
            "region": ["East", "East", "West", "West", "West"],
            "value": [10, 50, 20, 30, 100],
        }
    )
    result = rank(df, metric="value", group_by="region")
    assert "rank" in result.columns
    # East group: [10, 50] -> ranks [0.5, 1.0]
    assert abs(result.loc[0, "rank"] - 0.5) < 0.001
    assert abs(result.loc[1, "rank"] - 1.0) < 0.001
    # West group: [20, 30, 100] -> ranks [0.333..., 0.666..., 1.0]
    assert abs(result.loc[2, "rank"] - 0.3333) < 0.01
    assert abs(result.loc[3, "rank"] - 0.6666) < 0.01
    assert abs(result.loc[4, "rank"] - 1.0) < 0.001


def test_rank_with_single_group():
    """Rank with group_by should work when only one unique group value."""
    df = pd.DataFrame(
        {
            "region": ["East", "East", "East", "East", "East"],
            "value": [10, 50, 20, 30, 100],
        }
    )
    result = rank(df, metric="value", group_by="region")
    assert "rank" in result.columns
    expected = [0.2, 0.8, 0.4, 0.6, 1.0]
    for i, exp in enumerate(expected):
        assert abs(result["rank"].iloc[i] - exp) < 0.001


def test_rank_with_single_row():
    """Rank should work with a single row DataFrame."""
    df = pd.DataFrame({"value": [42]})
    result = rank(df, metric="value")
    assert "rank" in result.columns
    assert result["rank"].iloc[0] == 1.0


def test_rank_with_single_row_and_group():
    """Rank with group_by should work with a single row and single group."""
    df = pd.DataFrame({"region": ["East"], "value": [42]})
    result = rank(df, metric="value", group_by="region")
    assert "rank" in result.columns
    assert result["rank"].iloc[0] == 1.0


def test_rank_with_nulls():
    """Rank should handle null values in the metric column."""
    df = pd.DataFrame({"value": [10, None, 30, None, 50]})
    result = rank(df, metric="value")
    assert "rank" in result.columns
    assert abs(result["rank"].iloc[0] - 0.3333) < 0.01
    assert pd.isna(result["rank"].iloc[1])
    assert abs(result["rank"].iloc[2] - 0.6666) < 0.01
    assert pd.isna(result["rank"].iloc[3])
    assert abs(result["rank"].iloc[4] - 1.0) < 0.001


def test_rank_preserves_original_columns():
    """Rank should preserve all original columns in the DataFrame."""
    df = pd.DataFrame(
        {
            "x": ["a", "b", "a", "b", "a"],
            "y": ["c", "c", "d", "d", "c"],
            "value": [10, 20, 30, 40, 50],
        }
    )
    result = rank(df, metric="value")
    assert list(result.columns) == ["x", "y", "value", "rank"]
    assert result["x"].tolist() == ["a", "b", "a", "b", "a"]
    assert result["y"].tolist() == ["c", "c", "d", "d", "c"]


def test_rank_with_group_and_single_row_per_group():
    """Rank should work when each group has exactly one row."""
    df = pd.DataFrame(
        {
            "region": ["East", "West", "North", "South"],
            "value": [10, 20, 30, 40],
        }
    )
    result = rank(df, metric="value", group_by="region")
    assert "rank" in result.columns
    for i in range(len(df)):
        assert result["rank"].iloc[i] == 1.0


def test_rank_does_not_mutate_original():
    """Rank should not mutate the input DataFrame."""
    df = pd.DataFrame({"value": [10, 20, 30]})
    original_columns = list(df.columns)
    _ = rank(df.copy(), metric="value")
    assert list(df.columns) == original_columns
    assert "rank" not in df.columns


def test_rank_with_ties():
    """Rank should handle tied values correctly."""
    df = pd.DataFrame({"value": [10, 10, 20, 20, 30]})
    result = rank(df, metric="value")
    assert abs(result["rank"].iloc[0] - 0.3) < 0.001
    assert abs(result["rank"].iloc[1] - 0.3) < 0.001
    assert abs(result["rank"].iloc[2] - 0.7) < 0.001
    assert abs(result["rank"].iloc[3] - 0.7) < 0.001
    assert abs(result["rank"].iloc[4] - 1.0) < 0.001

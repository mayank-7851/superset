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
"""
Integration-style tests for the rank post-processing operation used by the
heatmap chart.  These tests exercise the same code path as `QueryObject.exec_post_processing`
when it encounters a ``rank`` operation — the same pipeline that the heatmap
chart's ``buildQuery.ts`` configures via ``rankOperator``.

The central regression: when a heatmap is filtered to a single region/category,
``rank`` previously used ``DataFrame.groupby().apply()``, which returns a
DataFrame (not a Series) for single-group cases, causing a ``ValueError`` when
assigning to ``df["rank"]``.  The fix uses ``.transform()`` which always returns
a Series.
"""
import numpy as np
import pandas as pd

from superset.utils.pandas_postprocessing import rank


class TestRankPostProcessingIntegration:
    """Integration-like tests for the rank post-processing operation.

    These directly exercise the ``rank`` function that is called by
    ``QueryObject.exec_post_processing`` when processing a heatmap query with
    ``post_processing: [{"operation": "rank", "options": {...}}]``.
    """

    def test_single_region_heatmap_with_group_by(self) -> None:
        """Simulates a heatmap filtered to one region with multiple products.

        This is the primary bug case: all rows share the same ``group_by``
        value (one region), which used to cause
        ``groupby().apply()`` to return a DataFrame instead of a Series.
        """
        # Simulates query result for heatmap filtered to region='West'
        df = pd.DataFrame(
            {
                "x_axis_column": ["West", "West", "West"],
                "groupby_column": ["Product A", "Product B", "Product C"],
                "metric": [100.0, 250.0, 175.0],
            }
        )
        result = rank(df.copy(), metric="metric", group_by="x_axis_column")
        assert "rank" in result.columns
        assert len(result) == 3
        # Ranks should be percentiles: [1/3, 3/3, 2/3] in order
        assert result["rank"].iloc[0] < result["rank"].iloc[2] < result["rank"].iloc[1]
        assert np.isclose(result["rank"].max(), 1.0)

    def test_single_category_heatmap_with_group_by(self) -> None:
        """Simulates a heatmap filtered to one category in the grouping dimension."""
        df = pd.DataFrame(
            {
                "x_axis_column": ["Region A", "Region B", "Region C"],
                "groupby_column": ["Shoes", "Shoes", "Shoes"],
                "metric": [300.0, 150.0, 450.0],
            }
        )
        result = rank(df.copy(), metric="metric", group_by="groupby_column")
        assert "rank" in result.columns
        assert len(result) == 3
        assert np.isclose(result["rank"].max(), 1.0)
        assert result["rank"].iloc[2] > result["rank"].iloc[1]  # 450 > 150

    def test_single_row_single_group_heatmap(self) -> None:
        """Simulates a 1×1 heatmap — single region, single product."""
        df = pd.DataFrame(
            {
                "x_axis_column": ["West"],
                "groupby_column": ["Product A"],
                "metric": [42.0],
            }
        )
        result = rank(df.copy(), metric="metric", group_by="x_axis_column")
        assert "rank" in result.columns
        assert len(result) == 1
        assert result["rank"].iloc[0] == 1.0

    def test_multiple_regions_heatmap_with_group_by(self) -> None:
        """Regression: ensure normal multi-group heatmaps still work."""
        df = pd.DataFrame(
            {
                "x_axis_column": [
                    "West", "West", "West",
                    "East", "East", "East",
                ],
                "groupby_column": [
                    "Product A", "Product B", "Product C",
                    "Product A", "Product B", "Product C",
                ],
                "metric": [100.0, 200.0, 150.0, 300.0, 250.0, 350.0],
            }
        )
        result = rank(df.copy(), metric="metric", group_by="x_axis_column")
        assert "rank" in result.columns
        assert len(result) == 6
        # Each group of 3 should have ranks in [~0.33, ~0.67, 1.0]
        west_ranks = result[result["x_axis_column"] == "West"]["rank"]
        east_ranks = result[result["x_axis_column"] == "East"]["rank"]
        for ranks in [west_ranks, east_ranks]:
            assert np.isclose(ranks.max(), 1.0)
            assert ranks.min() > 0.0

    def test_heatmap_no_group_by(self) -> None:
        """Heatmap without group_by (e.g. normalize_across='heatmap')."""
        df = pd.DataFrame(
            {
                "x_axis_column": ["West", "West", "East", "East"],
                "groupby_column": ["A", "B", "A", "B"],
                "metric": [100.0, 200.0, 150.0, 300.0],
            }
        )
        result = rank(df.copy(), metric="metric")
        assert "rank" in result.columns
        assert len(result) == 4
        assert np.isclose(result["rank"].max(), 1.0)

    def test_original_columns_preserved(self) -> None:
        """The rank function must not alter or remove original columns."""
        df = pd.DataFrame(
            {
                "x": ["West", "East"],
                "y": ["A", "B"],
                "m": [100.0, 200.0],
            }
        )
        original_columns = list(df.columns)
        result = rank(df.copy(), metric="m", group_by="x")
        assert list(result.columns) == original_columns + ["rank"]
        # All original values intact
        assert result["x"].tolist() == ["West", "East"]
        assert result["y"].tolist() == ["A", "B"]
        assert result["m"].tolist() == [100.0, 200.0]

    def test_with_null_metric_values(self) -> None:
        """Rank with some null metric values should not crash."""
        df = pd.DataFrame(
            {
                "x": ["West", "West", "West"],
                "y": ["A", "B", "C"],
                "m": [100.0, np.nan, 150.0],
            }
        )
        result = rank(df.copy(), metric="m", group_by="x")
        assert "rank" in result.columns
        assert np.isnan(result.loc[1, "rank"])

    def test_empty_dataframe_no_group_by(self) -> None:
        """Empty DataFrame should not cause a crash with group_by=None."""
        df = pd.DataFrame({"x": [], "y": [], "m": []})
        result = rank(df.copy(), metric="m")
        assert "rank" in result.columns
        assert len(result) == 0

    def test_empty_dataframe_with_group_by(self) -> None:
        """Empty DataFrame should not cause a crash with group_by set."""
        df = pd.DataFrame({"x": [], "y": [], "m": []})
        result = rank(df.copy(), metric="m", group_by="x")
        assert "rank" in result.columns
        assert len(result) == 0

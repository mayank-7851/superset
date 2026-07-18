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

from superset.utils import pandas_postprocessing as pp
from tests.unit_tests.fixtures.dataframes import categories_df


def test_rank_should_rank():
    # Here we use np.isclose to avoid "false positives" in != tests
    # Plain
    _categories_df = categories_df.copy(deep=True)
    assert np.isclose(
        pp.rank(_categories_df, "asc_idx")["rank"],
        np.linspace(1.0 / 101.0, 1.0, 101),
        rtol=1e-8,
    ).all()

    # Grouped
    gb = pp.rank(_categories_df, "asc_idx", "dept").groupby("dept")
    res = gb.apply(
        lambda x: np.isclose(
            x.sort_values("rank")["rank"],
            np.linspace(1.0 / len(x), 1.0, len(x)),
            rtol=1e-8,
        ).all()
    )
    assert res.all()


def test_rank_single_cat():
    # Check that reducing the category to one value still holds valid results
    _categories_df = categories_df.copy(deep=True)

    # This was raising up to 6.1.0, see https://github.com/apache/superset/issues/40709
    tmp_df = _categories_df[_categories_df["dept"] == "dept0"].reset_index(drop=True)
    pp.rank(tmp_df, "asc_idx", "dept")

    assert tmp_df["rank"].min() == 1.0 / len(tmp_df)
    assert tmp_df["rank"].max() == 1.0


def test_rank_single_row_with_group_by():
    """Rank should handle a single row with group_by without error."""
    import pandas as pd

    df = pd.DataFrame({"dept": ["dept0"], "value": [42]})
    result = pp.rank(df, "value", "dept")
    assert result["rank"].iloc[0] == 1.0
    assert len(result) == 1


def test_rank_single_row_no_group_by():
    """Rank should handle a single row without group_by."""
    import pandas as pd

    df = pd.DataFrame({"value": [42]})
    result = pp.rank(df, "value")
    assert result["rank"].iloc[0] == 1.0
    assert len(result) == 1


def test_rank_empty_dataframe():
    """Rank should handle an empty DataFrame gracefully."""
    import pandas as pd

    df = pd.DataFrame({"dept": pd.Series(dtype="str"), "value": pd.Series(dtype="float64")})
    result = pp.rank(df, "value", "dept")
    assert len(result) == 0
    assert "rank" in result.columns


def test_rank_all_null_metric_values():
    """Rank should handle a column where all metric values are null."""
    import pandas as pd

    df = pd.DataFrame({"dept": ["a", "a", "b"], "value": [np.nan, np.nan, np.nan]})
    result = pp.rank(df, "value", "dept")
    # All rank values should be NaN (pandas rank of all NaN produces NaN)
    assert result["rank"].isna().all()


def test_rank_mixed_null_metric_values():
    """Rank should handle mixed null and non-null metric values."""
    import pandas as pd

    df = pd.DataFrame(
        {"dept": ["a", "a", "a"], "value": [10, np.nan, 30]}
    )
    result = pp.rank(df, "value", "dept")
    # Non-null values should have valid ranks
    assert result.loc[0, "rank"] == 0.5  # lower of two non-null
    assert result.loc[2, "rank"] == 1.0  # higher of two non-null
    assert np.isnan(result.loc[1, "rank"])  # null stays null


def test_rank_group_by_column_all_same():
    """Rank with group_by where all rows have the same group value (like single region filter)."""
    import pandas as pd

    df = pd.DataFrame(
        {
            "region": ["East", "East", "East", "East", "East"],
            "sales": [100, 200, 300, 400, 500],
        }
    )
    result = pp.rank(df, "sales", "region")
    assert len(result) == 5
    assert "rank" in result.columns
    # Ranks should be evenly distributed 0.2, 0.4, 0.6, 0.8, 1.0
    assert result["rank"].min() == 0.2
    assert result["rank"].max() == 1.0
    assert np.isclose(result["rank"].iloc[0], 0.2)
    assert np.isclose(result["rank"].iloc[4], 1.0)


def test_rank_two_groups_one_row_each():
    """Rank with group_by where each group has exactly one row."""
    import pandas as pd

    df = pd.DataFrame(
        {
            "dept": ["dept0", "dept1"],
            "value": [10, 20],
        }
    )
    result = pp.rank(df, "value", "dept")
    # Each group has one row, so each rank should be 1.0
    assert (result["rank"] == 1.0).all()

/**
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */

/**
 * E2E test for #32: Heatmap chart crashes when filtered to a single region.
 *
 * When a user filters a heatmap chart to a single region or single category
 * in the grouping dimension, the chart used to crash with a database engine
 * error because the backend's rank post-processing operation would fail
 * when ``pandas.groupby().apply()`` returned a DataFrame instead of a Series
 * for single-group cases.
 *
 * The fix in ``superset/utils/pandas_postprocessing/rank.py`` replaces
 * ``.apply()`` with ``.transform()``, which always returns a Series.
 *
 * These tests verify:
 * - Filtering to a single region renders without error
 * - Filtering to a single category renders without error
 * - Normal multi-group heatmaps still work (regression guard)
 * - No sensitive error information is exposed in the UI
 */
import { testWithAssets, expect } from '../../helpers/fixtures';
import { apiPut } from '../../helpers/api/requests';
import { apiPostChart } from '../../helpers/api/chart';
import type { Page } from '@playwright/test';

const DATASET_NAME = 'birth_names';

interface ChartDataResponse {
  result?: Array<{
    data?: Array<Record<string, unknown>>;
    error?: string;
    stacktrace?: string;
    status?: string;
  }>;
  message?: string;
}

/**
 * Find a dataset ID by its table name.
 */
async function findBirthNamesDatasetId(page: Page): Promise<number> {
  const query = `(filters:!((col:table_name,opr:eq,value:'${DATASET_NAME}')))`;
  const resp = await page.request.get(`api/v1/dataset/?q=${query}`);
  const body = await resp.json();
  if (!body.result?.length) {
    throw new Error(`Dataset '${DATASET_NAME}' not found`);
  }
  return body.result[0].id;
}

/**
 * Build heatmap chart params.
 */
function buildHeatmapParams(datasetId: number) {
  return {
    datasource: `${datasetId}__table`,
    viz_type: 'heatmap',
    x_axis: 'gender',
    groupby: ['state'],
    metric: {
      aggregate: 'SUM',
      column: { column_name: 'num' },
      expressionType: 'SIMPLE',
      label: 'SUM(num)',
    },
    normalize_across: 'heatmap',
    linear_color_scheme: 'blue_white_yellow',
    legend_type: 'continuous',
    show_legend: true,
    show_percentage: false,
    show_values: true,
    row_limit: 100,
  };
}

/**
 * Query chart data and return the parsed response.
 */
async function getChartData(
  page: Page,
  chartId: number,
): Promise<ChartDataResponse> {
  const resp = await page.request.get(
    `api/v1/chart/${chartId}/data/?format=json&type=full`,
  );
  const body = await resp.json();
  expect(resp.ok()).toBe(true);
  return body as ChartDataResponse;
}

testWithAssets(
  'Heatmap renders with single region filter (single group in x_axis)',
  async ({ page, testAssets }) => {
    const datasetId = await findBirthNamesDatasetId(page);

    // Create a heatmap chart
    const chartResp = await apiPostChart(page, {
      slice_name: `heatmap_single_region_${Date.now()}`,
      datasource_id: datasetId,
      datasource_type: 'table',
      viz_type: 'heatmap',
      params: JSON.stringify(buildHeatmapParams(datasetId)),
    });
    expect(chartResp.ok()).toBe(true);
    const chartId: number = (await chartResp.json()).id;
    testAssets.trackChart(chartId);

    // First, verify the heatmap works without any filters (regression guard)
    const dataNoFilter = await getChartData(page, chartId);
    expect(dataNoFilter.result?.[0]?.status).toBeUndefined();
    // result array should exist and have data
    expect(dataNoFilter.result).toBeDefined();
    expect(dataNoFilter.result!.length).toBeGreaterThan(0);

    // Now add a filter to narrow to a single gender (e.g., 'boy')
    const params = buildHeatmapParams(datasetId);
    (params as any).adhoc_filters = [
      {
        clause: 'WHERE',
        expressionType: 'SIMPLE',
        subject: 'gender',
        operator: '==',
        comparator: 'boy',
      },
    ];

    await apiPut(page, `api/v1/chart/${chartId}`, {
      params: JSON.stringify(params),
    });

    const dataFiltered = await getChartData(page, chartId);
    expect(dataFiltered.result?.[0]?.status).toBeUndefined();

    // Verify the response does NOT contain error information
    const result = dataFiltered.result?.[0];
    if (result) {
      expect(result.error).toBeUndefined();
      expect(result.stacktrace).toBeUndefined();
    }
  },
);

testWithAssets(
  'Heatmap renders with single category filter (single group in groupby)',
  async ({ page, testAssets }) => {
    const datasetId = await findBirthNamesDatasetId(page);

    const chartResp = await apiPostChart(page, {
      slice_name: `heatmap_single_category_${Date.now()}`,
      datasource_id: datasetId,
      datasource_type: 'table',
      viz_type: 'heatmap',
      params: JSON.stringify(buildHeatmapParams(datasetId)),
    });
    expect(chartResp.ok()).toBe(true);
    const chartId: number = (await chartResp.json()).id;
    testAssets.trackChart(chartId);

    // Add a filter that narrows to a single state
    const params = buildHeatmapParams(datasetId);
    (params as any).adhoc_filters = [
      {
        clause: 'WHERE',
        expressionType: 'SIMPLE',
        subject: 'state',
        operator: '==',
        comparator: 'CA',
      },
    ];

    await apiPut(page, `api/v1/chart/${chartId}`, {
      params: JSON.stringify(params),
    });

    const dataFiltered = await getChartData(page, chartId);
    expect(dataFiltered.result?.[0]?.status).toBeUndefined();

    const result = dataFiltered.result?.[0];
    if (result) {
      expect(result.error).toBeUndefined();
      expect(result.stacktrace).toBeUndefined();
    }
  },
);

testWithAssets(
  'Heatmap with single region and normalized mode',
  async ({ page, testAssets }) => {
    const datasetId = await findBirthNamesDatasetId(page);

    const params = buildHeatmapParams(datasetId);
    (params as any).normalized = true;
    (params as any).normalize_across = 'x';

    const chartResp = await apiPostChart(page, {
      slice_name: `heatmap_normalized_single_${Date.now()}`,
      datasource_id: datasetId,
      datasource_type: 'table',
      viz_type: 'heatmap',
      params: JSON.stringify(params),
    });
    expect(chartResp.ok()).toBe(true);
    const chartId: number = (await chartResp.json()).id;
    testAssets.trackChart(chartId);

    // Verify it works normally with multiple groups
    const dataNormal = await getChartData(page, chartId);
    expect(dataNormal.result?.[0]?.status).toBeUndefined();

    // Now filter to single gender + add normalized
    const filteredParams = { ...params, adhoc_filters: [
      {
        clause: 'WHERE',
        expressionType: 'SIMPLE',
        subject: 'gender',
        operator: '==',
        comparator: 'boy',
      },
    ]};

    await apiPut(page, `api/v1/chart/${chartId}`, {
      params: JSON.stringify(filteredParams),
    });

    const dataFiltered = await getChartData(page, chartId);
    expect(dataFiltered.result?.[0]?.status).toBeUndefined();

    const result = dataFiltered.result?.[0];
    if (result) {
      expect(result.error).toBeUndefined();
    }
  },
);

testWithAssets(
  'Heatmap with single region: error messages do not expose sensitive internals',
  async ({ page, testAssets }) => {
    const datasetId = await findBirthNamesDatasetId(page);

    const params = buildHeatmapParams(datasetId);
    // Add a filter for a non-existent value - should not crash
    (params as any).adhoc_filters = [
      {
        clause: 'WHERE',
        expressionType: 'SIMPLE',
        subject: 'gender',
        operator: '==',
        comparator: 'nonexistent_value_xyz',
      },
    ];

    const chartResp = await apiPostChart(page, {
      slice_name: `heatmap_empty_data_${Date.now()}`,
      datasource_id: datasetId,
      datasource_type: 'table',
      viz_type: 'heatmap',
      params: JSON.stringify(params),
    });
    expect(chartResp.ok()).toBe(true);
    const chartId: number = (await chartResp.json()).id;
    testAssets.trackChart(chartId);

    const data = await getChartData(page, chartId);
    const result = data.result?.[0];

    // Should not contain raw database errors
    expect(result?.stacktrace).toBeUndefined();
    // If there's an error message, it should be user-friendly
    if (result?.error) {
      const errorText = String(result.error);
      // Should NOT contain raw SQL or stack traces
      expect(errorText).not.toContain('Traceback');
      expect(errorText).not.toContain('File "');
      expect(errorText).not.toContain('raise');
      // Should NOT expose table names from internal queries
      expect(errorText).not.toContain('FROM ');
      expect(errorText).not.toContain('SELECT ');
    }
  },
);

testWithAssets(
  'Heatmap rapid filter changes: switching between single and multiple groups',
  async ({ page, testAssets }) => {
    const datasetId = await findBirthNamesDatasetId(page);

    const chartResp = await apiPostChart(page, {
      slice_name: `heatmap_rapid_filter_${Date.now()}`,
      datasource_id: datasetId,
      datasource_type: 'table',
      viz_type: 'heatmap',
      params: JSON.stringify(buildHeatmapParams(datasetId)),
    });
    expect(chartResp.ok()).toBe(true);
    const chartId: number = (await chartResp.json()).id;
    testAssets.trackChart(chartId);

    // Rapidly alternate between single-group and multi-group filters
    const singleGroupFilter = [
      {
        clause: 'WHERE',
        expressionType: 'SIMPLE',
        subject: 'gender',
        operator: '==',
        comparator: 'boy',
      },
    ];
    const multiGroupFilter: typeof singleGroupFilter = [];

    for (let i = 0; i < 5; i += 1) {
      const filterToUse = i % 2 === 0 ? singleGroupFilter : multiGroupFilter;
      const params = buildHeatmapParams(datasetId);
      (params as any).adhoc_filters = filterToUse;

      await apiPut(page, `api/v1/chart/${chartId}`, {
        params: JSON.stringify(params),
      });

      const data = await getChartData(page, chartId);
      // No crash, no error
      expect(data.result?.[0]?.status).toBeUndefined();
      const result = data.result?.[0];
      if (result) {
        expect(result.error).toBeUndefined();
      }
    }
  },
);

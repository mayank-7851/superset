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
import { isPostProcessingRank, QueryFormData } from '@superset-ui/core';
import buildQuery from '../../src/Heatmap/buildQuery';

const baseFormData = {
  datasource: '5__table',
  granularity_sqla: 'ds',
  metric: 'count',
  x_axis: 'category',
  groupby: ['region'],
  viz_type: 'heatmap',
} as QueryFormData;

const getQuery = (formData: QueryFormData) => buildQuery(formData).queries[0];
const getRankOperation = (formData: QueryFormData) =>
  getQuery(formData).post_processing?.find(isPostProcessingRank);

test('adds X axis orderby when sorting alphabetically ascending', () => {
  const query = getQuery({
    ...baseFormData,
    sort_x_axis: 'alpha_asc',
  });

  expect(query.orderby).toEqual([['category', true]]);
});

test('adds Y axis orderby when sorting alphabetically descending', () => {
  const query = getQuery({
    ...baseFormData,
    sort_y_axis: 'alpha_desc',
  });

  expect(query.orderby).toEqual([['region', false]]);
});

test('should ALWAYS include rank operation when normalized=true', () => {
  const rankOperation = getRankOperation({
    ...baseFormData,
    normalized: true,
  });

  expect(rankOperation).toBeDefined();
  expect(rankOperation?.operation).toBe('rank');
});

test('should ALWAYS include rank operation when normalized=false', () => {
  const rankOperation = getRankOperation({
    ...baseFormData,
    normalized: false,
  });

  expect(rankOperation).toBeDefined();
  expect(rankOperation?.operation).toBe('rank');
});

test('should ALWAYS include rank operation when normalized is undefined', () => {
  const rankOperation = getRankOperation({
    ...baseFormData,
    // normalized not set
  });

  expect(rankOperation).toBeDefined();
  expect(rankOperation?.operation).toBe('rank');
});

test('group_by should be undefined when normalize_across is "heatmap"', () => {
  const rankOperation = getRankOperation({
    ...baseFormData,
    normalize_across: 'heatmap',
  });

  expect(rankOperation).toBeDefined();
  expect(rankOperation?.options?.group_by).toBeUndefined();
});

test('group_by should be x_axis column label when normalize_across is "x"', () => {
  const rankOperation = getRankOperation({
    ...baseFormData,
    normalize_across: 'x',
  });

  expect(rankOperation).toBeDefined();
  expect(rankOperation?.options?.group_by).toBe('category');
});

test('group_by should be groupby column label when normalize_across is "y"', () => {
  const rankOperation = getRankOperation({
    ...baseFormData,
    normalize_across: 'y',
  });

  expect(rankOperation).toBeDefined();
  expect(rankOperation?.options?.group_by).toBe('region');
});

test('group_by from groupby works with a single groupby value', () => {
  const rankOperation = getRankOperation({
    ...baseFormData,
    groupby: ['region'],
    normalize_across: 'y',
  });

  expect(rankOperation).toBeDefined();
  expect(rankOperation?.options?.group_by).toBe('region');
});

test('group_by from groupby works with multiple groupby values (uses first)', () => {
  const rankOperation = getRankOperation({
    ...baseFormData,
    groupby: ['region', 'sub_region'],
    normalize_across: 'y',
  });

  expect(rankOperation).toBeDefined();
  expect(rankOperation?.options?.group_by).toBe('region');
});

test('group_by is undefined for normalize_across y with no groupby', () => {
  const rankOperation = getRankOperation({
    ...baseFormData,
    groupby: [],
    normalize_across: 'y',
  });

  expect(rankOperation).toBeDefined();
  expect(rankOperation?.options?.group_by).toBeUndefined();
});

test('group_by is undefined for normalize_across y with undefined groupby', () => {
  const rankOperation = getRankOperation({
    ...baseFormData,
    groupby: undefined,
    normalize_across: 'y',
  });

  expect(rankOperation).toBeDefined();
  expect(rankOperation?.options?.group_by).toBeUndefined();
});

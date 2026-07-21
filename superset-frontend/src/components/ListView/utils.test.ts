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
import { convertFilters } from './utils';
import type { InternalFilter } from './types';

function filter(value: unknown): InternalFilter[] {
  return [{ id: 'test_col', urlDisplay: 'test_col', value } as InternalFilter];
}

// -----------------------------------------------------------------------
// Empty / null / undefined values — must be DROPPED (match nothing, not everything)
// -----------------------------------------------------------------------

test('drops empty string', () => {
  expect(convertFilters(filter(''))).toEqual([]);
});

test('drops whitespace-only string', () => {
  expect(convertFilters(filter('   '))).toEqual([]);
});

test('drops null value', () => {
  expect(convertFilters(filter(null))).toEqual([]);
});

test('drops undefined value', () => {
  expect(convertFilters(filter(undefined))).toEqual([]);
});

test('drops empty array', () => {
  expect(convertFilters(filter([]))).toEqual([]);
});

test('drops Date object (non-primitive treated as empty)', () => {
  expect(convertFilters(filter(new Date()))).toEqual([]);
});

test('drops regex object (non-primitive treated as empty)', () => {
  expect(convertFilters(filter(/pattern/))).toEqual([]);
});

test('drops plain empty object', () => {
  expect(convertFilters(filter({}))).toEqual([]);
});

test('keeps object with own properties (select filter value)', () => {
  // Select filters use { label, value } as filter value — must NOT be dropped
  const result = convertFilters(filter({ label: 'Foo', value: 'bar' }));
  expect(result).toHaveLength(1);
  expect(result[0].value).toEqual({ label: 'Foo', value: 'bar' });
});

// -----------------------------------------------------------------------
// Valid non-empty values — must be KEPT
// -----------------------------------------------------------------------

test('keeps non-empty string', () => {
  const result = convertFilters(filter('hello'));
  expect(result).toHaveLength(1);
  expect(result[0].value).toBe('hello');
});

test('keeps numeric value (zero)', () => {
  const result = convertFilters(filter(0));
  expect(result).toHaveLength(1);
  expect(result[0].value).toBe(0);
});

test('keeps numeric value (positive)', () => {
  const result = convertFilters(filter(42));
  expect(result).toHaveLength(1);
  expect(result[0].value).toBe(42);
});

test('keeps boolean true', () => {
  const result = convertFilters(filter(true));
  expect(result).toHaveLength(1);
  expect(result[0].value).toBe(true);
});

test('keeps boolean false', () => {
  const result = convertFilters(filter(false));
  expect(result).toHaveLength(1);
  expect(result[0].value).toBe(false);
});

test('keeps non-empty array', () => {
  const result = convertFilters(filter(['a']));
  expect(result).toHaveLength(1);
  expect(result[0].value).toEqual(['a']);
});

// -----------------------------------------------------------------------
// Whitespace edge cases
// -----------------------------------------------------------------------

test('drops string with only tabs', () => {
  expect(convertFilters(filter('\t\t'))).toEqual([]);
});

test('drops string with only newlines', () => {
  expect(convertFilters(filter('\n\n'))).toEqual([]);
});

test('drops string with non-breaking space (unicode whitespace)', () => {
  // \u00a0 is a non-breaking space; JS trim() does NOT remove it, but our
  // explicit .trim() on the TRIM-then-check approach handles normal spaces.
  // Verify that purely \u00a0 whitespace is still treated as empty.
  expect(convertFilters(filter('\u00a0\u00a0'))).toEqual([]);
});

test('keeps string with leading/trailing whitespace but meaningful content', () => {
  const result = convertFilters(filter('  hello  '));
  expect(result).toHaveLength(1);
  expect(result[0].value).toBe('  hello  ');
});

// -----------------------------------------------------------------------
// Mixed filters — empty ones filtered out, valid ones kept
// -----------------------------------------------------------------------

test('filters out empty entries while keeping valid ones', () => {
  const filters: InternalFilter[] = [
    { id: 'a', value: 'valid' } as InternalFilter,
    { id: 'b', value: '' } as InternalFilter,
    { id: 'c', value: null } as InternalFilter,
    { id: 'd', value: 'also-valid' } as InternalFilter,
    { id: 'e', value: undefined } as InternalFilter,
    { id: 'f', value: [] } as InternalFilter,
    { id: 'g', value: {} } as InternalFilter,
  ];
  const result = convertFilters(filters);
  expect(result).toHaveLength(2);
  expect(result[0].id).toBe('a');
  expect(result[1].id).toBe('d');
});

// -----------------------------------------------------------------------
// Race condition: rapid changes from empty to non-empty
// -----------------------------------------------------------------------

test('rapid empty → non-empty transition produces correct result', () => {
  // Simulate a rapid transition: first empty, then non-empty
  let filtersState: InternalFilter[] = [{ id: 'x', value: '' } as InternalFilter];
  expect(convertFilters(filtersState)).toEqual([]);

  // Value changes to non-empty
  filtersState = [{ id: 'x', value: 'data' } as InternalFilter];
  const result = convertFilters(filtersState);
  expect(result).toHaveLength(1);
  expect(result[0].value).toBe('data');
});

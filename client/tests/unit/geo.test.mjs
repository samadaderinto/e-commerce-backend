import test from 'node:test';
import assert from 'node:assert/strict';
import {
  COUNTRIES,
  US_SUBDIVISIONS,
  resolveCountry,
  resolveSubdivision,
  validatePostalCode,
  parseAddressLines,
  composeAddress,
  validateStreetAddress,
  validateUnit,
  validateCity,
  SUPPORTED_COUNTRY_CODE,
  DEFAULT_COUNTRY_NAME,
} from '../../src/lib/geo.ts';

test('COUNTRIES catalog defaults and accessibility guardrails', () => {
  assert.ok(COUNTRIES.length > 50, 'Has comprehensive list of global countries');

  const us = COUNTRIES.find((c) => c.code === 'US');
  assert.ok(us, 'United States is in catalog');
  assert.strictEqual(us.isSupported, true, 'United States is enabled');
  assert.strictEqual(us.name, DEFAULT_COUNTRY_NAME);

  const disabledCountries = COUNTRIES.filter((c) => c.code !== 'US');
  assert.ok(disabledCountries.length > 0);
  assert.ok(
    disabledCountries.every((c) => c.isSupported === false),
    'All non-US countries are disabled in Phase 1',
  );
});

test('US subdivisions includes all 50 states, DC, 5 territories, and 3 Armed Forces regions', () => {
  assert.strictEqual(US_SUBDIVISIONS.length, 59, '50 states + DC + 5 territories + 3 Armed Forces regions');

  // Verify key states
  assert.ok(US_SUBDIVISIONS.find((s) => s.code === 'CA' && s.name === 'California'));
  assert.ok(US_SUBDIVISIONS.find((s) => s.code === 'NY' && s.name === 'New York'));
  assert.ok(US_SUBDIVISIONS.find((s) => s.code === 'FL' && s.name === 'Florida'));
  assert.ok(US_SUBDIVISIONS.find((s) => s.code === 'DC' && s.name === 'District of Columbia'));
  assert.ok(US_SUBDIVISIONS.find((s) => s.code === 'PR' && s.name === 'Puerto Rico'));
  assert.ok(US_SUBDIVISIONS.find((s) => s.code === 'AA' && s.name === 'Armed Forces Americas'));
  assert.ok(US_SUBDIVISIONS.find((s) => s.code === 'AE' && s.name === 'Armed Forces Europe / Africa / Middle East'));
  assert.ok(US_SUBDIVISIONS.find((s) => s.code === 'AP' && s.name === 'Armed Forces Pacific'));
});

test('resolveCountry resolves US and aliases properly', () => {
  assert.strictEqual(resolveCountry(null).code, 'US');
  assert.strictEqual(resolveCountry('').code, 'US');
  assert.strictEqual(resolveCountry('US').code, 'US');
  assert.strictEqual(resolveCountry('USA').code, 'US');
  assert.strictEqual(resolveCountry('United States').code, 'US');
  assert.strictEqual(resolveCountry('United States of America').code, 'US');
});

test('resolveSubdivision matches by code, name, or formatted label', () => {
  assert.strictEqual(resolveSubdivision('CA', 'US')?.name, 'California');
  assert.strictEqual(resolveSubdivision('California', 'US')?.code, 'CA');
  assert.strictEqual(resolveSubdivision('California (CA)', 'US')?.code, 'CA');
  assert.strictEqual(resolveSubdivision('FL', 'US')?.name, 'Florida');
  assert.strictEqual(resolveSubdivision('Florida', 'US')?.code, 'FL');
});

test('validatePostalCode handles US 5-digit and ZIP+4 formats', () => {
  // Valid US 5-digit
  const v1 = validatePostalCode('90210', 'US');
  assert.strictEqual(v1.valid, true);

  // Valid US ZIP+4
  const v2 = validatePostalCode('90210-1234', 'US');
  assert.strictEqual(v2.valid, true);

  // Invalid formats
  assert.strictEqual(validatePostalCode('9021', 'US').valid, false);
  assert.strictEqual(validatePostalCode('902100', 'US').valid, false);
  assert.strictEqual(validatePostalCode('90210-12', 'US').valid, false);
  assert.strictEqual(validatePostalCode('ABCDE', 'US').valid, false);
  assert.strictEqual(validatePostalCode('', 'US').valid, false);
});

test('validatePostalCode handles UK and Nigeria postal formats', () => {
  // UK formats
  assert.strictEqual(validatePostalCode('SW1A 1AA', 'GB').valid, true);
  assert.strictEqual(validatePostalCode('W1A 0AX', 'GB').valid, true);
  assert.strictEqual(validatePostalCode('12345', 'GB').valid, false);

  // Nigeria formats
  assert.strictEqual(validatePostalCode('102103', 'NG').valid, true);
  assert.strictEqual(validatePostalCode('10210', 'NG').valid, false);
  assert.strictEqual(validatePostalCode('1021033', 'NG').valid, false);
});

test('parseAddressLines separates street and secondary unit specifiers', () => {
  // Comma-separated apartment
  const res1 = parseAddressLines('742 Evergreen Terrace, Apt 4B');
  assert.strictEqual(res1.street, '742 Evergreen Terrace');
  assert.strictEqual(res1.unit, 'Apt 4B');

  // Suite specifier
  const res2 = parseAddressLines('123 Market Street, Suite 300');
  assert.strictEqual(res2.street, '123 Market Street');
  assert.strictEqual(res2.unit, 'Suite 300');

  // Newline-separated unit
  const res3 = parseAddressLines('456 Elm Way\nUnit 12');
  assert.strictEqual(res3.street, '456 Elm Way');
  assert.strictEqual(res3.unit, 'Unit 12');

  // Single-line street without unit
  const res4 = parseAddressLines('1600 Pennsylvania Avenue NW');
  assert.strictEqual(res4.street, '1600 Pennsylvania Avenue NW');
  assert.strictEqual(res4.unit, '');

  // Null / empty safety
  assert.deepStrictEqual(parseAddressLines(''), { street: '', unit: '' });
  assert.deepStrictEqual(parseAddressLines(null), { street: '', unit: '' });
});

test('composeAddress joins street and optional unit cleanly', () => {
  assert.strictEqual(
    composeAddress('742 Evergreen Terrace', 'Apt 4B'),
    '742 Evergreen Terrace, Apt 4B',
  );
  assert.strictEqual(
    composeAddress('742 Evergreen Terrace', ''),
    '742 Evergreen Terrace',
  );
  assert.strictEqual(
    composeAddress('742 Evergreen Terrace', null),
    '742 Evergreen Terrace',
  );
  assert.strictEqual(
    composeAddress('  123 Market St  ', '  Suite 2  '),
    '123 Market St, Suite 2',
  );
});

test('validateStreetAddress enforces min length and sanitization', () => {
  // Valid
  const v1 = validateStreetAddress('742 Evergreen Terrace');
  assert.strictEqual(v1.valid, true);
  assert.strictEqual(v1.formatted, '742 Evergreen Terrace');

  // HTML sanitization (< and > stripped)
  const v2 = validateStreetAddress('<script>742 Evergreen Ter</script>');
  assert.strictEqual(v2.valid, true);
  assert.ok(!v2.formatted.includes('<') && !v2.formatted.includes('>'));

  // Invalid: too short (< 5 chars)
  const v3 = validateStreetAddress('123');
  assert.strictEqual(v3.valid, false);
  assert.ok(v3.error?.includes('at least 5 characters'));

  // Invalid: empty
  const v4 = validateStreetAddress('');
  assert.strictEqual(v4.valid, false);
  assert.strictEqual(v4.error, 'Street address is required.');
});

test('validateUnit enforces max 30 character limit and sanitizes', () => {
  // Valid optional empty
  assert.strictEqual(validateUnit('').valid, true);
  assert.strictEqual(validateUnit('Apt 4B').valid, true);
  assert.strictEqual(validateUnit('Suite 300, Bldg 2').valid, true);

  // Sanitization
  const s = validateUnit('<b>Unit 10</b>');
  assert.strictEqual(s.valid, true);
  assert.strictEqual(s.formatted, 'bUnit 10/b');

  // Too long (> 30 chars)
  const longUnit = 'Apt 123456789012345678901234567890';
  const v = validateUnit(longUnit);
  assert.strictEqual(v.valid, false);
  assert.ok(v.error?.includes('30 characters or fewer'));
});

test('validateCity checks required city name and allowed characters', () => {
  assert.strictEqual(validateCity('Springfield').valid, true);
  assert.strictEqual(validateCity("St. John's").valid, true);
  assert.strictEqual(validateCity('Winston-Salem').valid, true);
  assert.strictEqual(validateCity('New York City').valid, true);

  // Empty
  assert.strictEqual(validateCity('').valid, false);

  // Invalid characters
  assert.strictEqual(validateCity('City<script>').valid, false);
  assert.strictEqual(validateCity('City#1').valid, false);
});


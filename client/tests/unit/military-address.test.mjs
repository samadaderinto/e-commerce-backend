import assert from 'node:assert/strict';
import { test } from 'node:test';
import { isMilitaryAddress, validateMilitaryAddress } from '../../src/lib/geo.ts';

test('military regions require consistent city, state and precise ZIP blocks', () => {
  for (const [state, zip] of [
    ['AA', '34012'],
    ['AE', '09012'],
    ['AP', '96213-1234'],
  ]) {
    assert.equal(validateMilitaryAddress({ city: 'APO', state, zip, country: 'US' }), undefined);
    assert.equal(isMilitaryAddress({ city: 'APO', state, zip, country: 'US' }), true);
  }

  for (const address of [
    { city: 'Djibouti', state: 'AE', zip: '09012', country: 'US' },
    { city: 'APO', state: 'CA', zip: '90210', country: 'US' },
    { city: 'APO', state: 'AE', zip: '90210', country: 'US' },
  ]) {
    assert.ok(validateMilitaryAddress(address));
  }

  for (const zip of ['34102', '96001']) {
    assert.equal(isMilitaryAddress({ zip, country: 'US' }), false);
  }

  assert.equal(
    validateMilitaryAddress({
      city: 'Montpellier',
      state: 'Occitanie',
      zip: '34000',
      country: 'France',
    }),
    undefined
  );
});

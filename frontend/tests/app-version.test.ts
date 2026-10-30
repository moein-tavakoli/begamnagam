import assert from 'node:assert/strict';
import { test } from 'node:test';
import { newerVersion } from '../lib/app-version.ts';

test('update notice compares numeric versions rather than strings',()=>{
  for(const next of ['0.15.1','0.16.0','0.100.0','1.0.0'])assert.equal(newerVersion(next,'0.15.0'),true,next);
  for(const next of ['0.15.0','0.14.99','0.9.0',null,{},'0.16','۱۴.۱.۰','0.16.0-preview','https://other.invalid'])assert.equal(newerVersion(next,'0.15.0'),false,String(next));
});

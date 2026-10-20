import test from 'node:test';
import assert from 'node:assert/strict';
import {qualificationHeaders} from './browser/qualification-headers.mjs';

for (const origin of ['http://localhost:3431','https://robot.onesa.eu']) {
 test(`ordinary ${origin} tests exclude hosting UI without an authority header`,()=>{
  const headers=qualificationHeaders(origin);
  assert.equal(headers['x-vercel-skip-toolbar'],'1');
  assert.equal(headers['x-vercel-protection-bypass'],undefined);
 });
}
for (const origin of ['http://localhost:3431','https://example.com','https://onesa-ai-platform-test.vercel.app','https://onesa-ai-robot-test.vercel.app.evil.invalid','https://onesa-ai-robot-test.vercel.app/path','https://user@onesa-ai-robot-test.vercel.app']) {
 test(`automation authority rejects an unintended target: ${origin}`,()=>{
  assert.throws(()=>qualificationHeaders(origin,'synthetic-test-only'),/verified Robot Preview origin/);
 });
}
test('verified Preview automation retains protection access and excludes the hosting toolbar',()=>{
 const headers=qualificationHeaders('https://onesa-ai-robot-example-druhustles-projects.vercel.app','synthetic-test-only');
 assert.equal(headers['x-vercel-protection-bypass'],'synthetic-test-only');
 assert.equal(headers['x-vercel-skip-toolbar'],'1');
});

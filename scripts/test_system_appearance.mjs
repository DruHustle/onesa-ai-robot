import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import {test} from 'node:test';
const root=new URL('../',import.meta.url);
const foundation=await readFile(new URL('onesa-ai-robot-frontend/public/onesa-foundation.css',root),'utf8');
const manifest=JSON.parse(await readFile(new URL('docs/engineering/design-system.consumer.json',root),'utf8'));
test('the Robot consumes the exact pinned shared foundation',()=>{assert.equal(createHash('sha256').update(foundation).digest('hex'),manifest.sha256);assert.equal(manifest.version,'1.0.0');assert.match(foundation,/@media \(prefers-color-scheme: dark\)/);assert.match(foundation,/color-scheme: light/);});
test('public and operator appearance have no clock or persisted theme dependency',async()=>{for(const file of ['index.html','console.html','theme.css','app.js']){const source=await readFile(new URL('onesa-ai-robot-frontend/public/'+file,root),'utf8');assert.doesNotMatch(source,/automatic-day-night|data-theme|OnesaDayNight|getHours\(|localStorage\.|sessionStorage\./);if(file.endsWith('.html')){assert.match(source,/data-onesa-product="robot"/);assert.match(source,/onesa-foundation\.css/);}}});
test('public product page cannot start private telemetry or session requests',async()=>{const source=await readFile(new URL('onesa-ai-robot-frontend/public/index.html',root),'utf8');assert.doesNotMatch(source,/<script|api\/v1|id="operator"|id="position"|id="history"/);assert.match(source,/STATIC ILLUSTRATION/);});

test('independent frontend build manifest matches the engineering consumer record',async()=>{const local=JSON.parse(await readFile(new URL('onesa-ai-robot-frontend/design-system.consumer.json',root),'utf8'));assert.deepEqual(local,manifest);const registry=await readFile(new URL('onesa-ai-robot-frontend/onesa-applications.json',root));assert.equal(createHash('sha256').update(registry).digest('hex'),manifest.applications.sha256);});

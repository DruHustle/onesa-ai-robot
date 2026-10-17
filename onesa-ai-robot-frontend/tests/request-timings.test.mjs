import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequestTimings} from './browser/request-timings.mjs';
const request=(path,method='GET')=>({url:()=>path,method:()=>method});
const origin='https://robot.example';
test('a stalled navigation remains visible without a response or failure event',()=>{
 let time=0;const r=createRequestTimings(origin,()=>time),q=request(origin+'/console');r.started(q);time=30000;
 assert.deepEqual(r.snapshot().pending,[{route:'/console',method:'GET',started_ms:0,elapsed_ms:30000}]);
 assert.equal(r.snapshot().recent[0].phase,'started');
});
test('records headers and terminal phases while clearing completed pending requests',()=>{
 let time=0;const r=createRequestTimings(origin,()=>time),q=request(origin+'/app.js');r.started(q);time=10;r.headers({request:()=>q,status:()=>200});time=20;r.finished(q);r.lifecycle('load');
 assert.deepEqual(r.snapshot().recent.map(x=>x.phase),['started','headers','complete','load']);assert.equal(r.snapshot().pending.length,0);
 const failed=request(origin+'/theme.css');r.started(failed);r.failed(failed);assert.equal(r.snapshot().recent.at(-1).phase,'transport_failed');assert.equal(r.snapshot().pending.length,0);
});
test('redacts task IDs and queries and never inspects credentials, headers or bodies',()=>{
 const r=createRequestTimings(origin,()=>0),id='12345678-1234-1234-1234-123456789abc';const q=request(origin+'/api/v1/tasks/'+id+'/approve?secret=private','POST');
 q.headers=q.postData=()=>{throw Error('credentials inspected');};r.started(q);const output=JSON.stringify(r.snapshot());assert.ok(output.includes('/api/v1/tasks/:task/approve'));assert.ok(!output.includes(id));assert.ok(!output.includes('private'));
});
test('ignores off-origin, unknown, malformed and arbitrary identifier paths',()=>{
 const r=createRequestTimings(origin,()=>0);for(const url of ['https://other.example/console',origin+'/api/v1/private-person',origin+'/unknown','invalid'])r.started(request(url));r.lifecycle('private');assert.deepEqual(r.snapshot(),{recent:[],pending:[]});
});
test('bounds pending and recent entries and returns detached snapshots',()=>{
 const r=createRequestTimings(origin,()=>0);for(let i=0;i<60;i++)r.started(request(origin+'/console'));const s=r.snapshot();assert.equal(s.pending.length,40);assert.equal(s.recent.length,40);s.recent[0].route='mutated';assert.equal(r.snapshot().recent[0].route,'/console');
});

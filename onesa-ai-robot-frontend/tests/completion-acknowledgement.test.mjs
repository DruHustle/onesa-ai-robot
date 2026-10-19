import test from 'node:test';
import assert from 'node:assert/strict';
import {isCompletedTaskResponse} from './browser/simulation-acceptance.mjs';
const origin='https://robot.example', id='owned-task';
function response({url=origin+'/api/v1/tasks',method='GET',status=200,body={tasks:[{id,state:'completed'}]},invalidJSON=false}={}) {
 return {url:()=>url,request:()=>({method:()=>method}),status:()=>status,json:async()=>{if(invalidJSON)throw new Error('Synthetic malformed JSON');return body;}};
}
test('only the actual completed owned-task response acknowledges completion',async()=>{
 assert.equal(await isCompletedTaskResponse(response(),origin,id),true);
});
for(const status of [401,403,503])test(`HTTP${status} never acknowledges completion`,async()=>{
 assert.equal(await isCompletedTaskResponse(response({status}),origin,id),false);
});
for(const body of [{tasks:[{id:'another-task',state:'completed'}]},{tasks:[{id,state:'running'}]}])test('another task or unfinished task never acknowledges completion '+JSON.stringify(body),async()=>{
 assert.equal(await isCompletedTaskResponse(response({body}),origin,id),false);
});
test('wrong origin, route and mutation responses are excluded',async()=>{
 for(const value of [{url:'https://unrelated.example/api/v1/tasks'},{url:origin+'/api/v1/status'},{method:'POST'}])assert.equal(await isCompletedTaskResponse(response(value),origin,id),false);
});
test('malformed task payloads are rejected',async()=>{
 for(const value of [{invalidJSON:true},{body:{}},{body:{tasks:{}}}])assert.equal(await isCompletedTaskResponse(response(value),origin,id),false);
});

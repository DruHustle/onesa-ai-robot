import test from 'node:test';
import assert from 'node:assert/strict';
import {cleanupOperatorSession} from './browser/session-cleanup.mjs';

function fixture(cookies, replies=[]) {
 const calls=[];
 const request=method=>async(path,options)=>{
  calls.push({method,path,options});
  const reply=replies.shift();assert.ok(reply,'Unexpected protected request');
  return {status:()=>reply.status,json:async()=>reply.body};
 };
 return {calls,page:{context:()=>({cookies:async origin=>{assert.equal(origin,'https://robot.example');return cookies;}}),request:{get:request('GET'),post:request('POST')}}};
}
test('anonymous public and unrelated-cookie fixtures make no protected request',async()=>{
 for(const cookies of [[],[{name:'unrelated',value:'synthetic'}]]){
  const {page,calls}=fixture(cookies);await cleanupOperatorSession(page,'https://robot.example');assert.deepEqual(calls,[]);
 }
});
test('owned session cleanup confirms logout and revocation with bounded requests',async()=>{
 const {page,calls}=fixture([{name:'robot_session',value:'synthetic'}],[{status:200,body:{csrf:'synthetic-csrf'}},{status:200},{status:401}]);
 await cleanupOperatorSession(page,'https://robot.example');
 assert.deepEqual(calls.map(c=>[c.method,c.path]),[['GET','/api/v1/auth/me'],['POST','/api/v1/auth/logout'],['GET','/api/v1/auth/me']]);
 assert.ok(calls.every(c=>c.options.timeout===10000));
 assert.deepEqual(calls[1].options.headers,{Origin:'https://robot.example','X-CSRF-Token':'synthetic-csrf'});
});
test('expired session does not submit another logout',async()=>{
 const {page,calls}=fixture([{name:'robot_session'}],[{status:401}]);await cleanupOperatorSession(page,'https://robot.example');assert.equal(calls.length,1);
});
test('unavailable session, missing CSRF, failed logout and failed revocation remain failures',async()=>{
 for(const replies of [[{status:503}],[{status:200,body:{}}],[{status:200,body:{csrf:'synthetic'}},{status:503}],[{status:200,body:{csrf:'synthetic'}},{status:200},{status:200}]]){
  const {page}=fixture([{name:'robot_session'}],replies);await assert.rejects(cleanupOperatorSession(page,'https://robot.example'),/Operator cleanup/);
 }
});

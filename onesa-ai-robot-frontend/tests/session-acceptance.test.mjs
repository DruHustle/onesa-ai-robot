import test from 'node:test';
import assert from 'node:assert/strict';
import {reloadWithSessionAcknowledgement,signOutWithAcknowledgement} from './browser/session-acceptance.mjs';
function fixture({status=200,body={csrf:'synthetic'},delay=0,timeout=false}={}) {
 const calls=[];let deliver,listening=false;
 const page={waitForResponse(predicate,options){
  calls.push(['observe',options.timeout]);listening=true;
  return new Promise((resolve,reject)=>{deliver=(path,method)=>setTimeout(()=>{
   if(timeout){reject(new Error('Synthetic observation timeout'));return;}
   const response={url:()=>`https://robot.example${path}`,request:()=>({method:()=>method}),status:()=>status,json:async()=>body};
   assert.equal(predicate({...response,url:()=> 'https://robot.example/api/v1/status'}),false);
   assert.equal(predicate({...response,request:()=>({method:()=> method==='GET'?'POST':'GET'})}),false);
   assert.equal(predicate(response),true);resolve(response);
  },delay);});
 },reload:async()=>{assert.equal(listening,true);calls.push(['reload']);deliver('/api/v1/auth/me','GET');},
 getByRole:(role,options)=>{assert.equal(role,'button');assert.equal(options.name,'Sign out');return {click:async()=>{assert.equal(listening,true);calls.push(['click']);deliver('/api/v1/auth/logout','POST');}}}};
 return {page,calls};
}
test('reload waits for its existing delayed session response',async()=>{
 const {page,calls}=fixture({delay:25});await reloadWithSessionAcknowledgement(page);
 assert.deepEqual(calls,[['observe',10000],['reload']]);
});
test('logout waits for signed_out before cleanup without issuing extra API requests',async()=>{
 const {page,calls}=fixture({delay:25,body:{status:'signed_out'}});await signOutWithAcknowledgement(page);
 assert.deepEqual(calls,[['observe',10000],['click']]);
});
for(const status of [401,403,503])test(`HTTP ${status} remains a failed acknowledgement`,async()=>{
 const {page}=fixture({status});await assert.rejects(reloadWithSessionAcknowledgement(page),new RegExp(`HTTP ${status}`));
});
test('missing CSRF and incorrect logout response remain failures',async()=>{
 await assert.rejects(reloadWithSessionAcknowledgement(fixture({body:{}}).page),/missing CSRF/);
 await assert.rejects(signOutWithAcknowledgement(fixture({body:{status:'pending'}}).page),/missing signed_out/);
});
test('observation timeout is bounded and never retried',async()=>{
 const {page,calls}=fixture({timeout:true});await assert.rejects(reloadWithSessionAcknowledgement(page),/timeout/);
 assert.deepEqual(calls,[['observe',10000],['reload']]);
});

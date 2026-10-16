import {test} from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {spawn} from 'node:child_process';
import {performance} from 'node:perf_hooks';

async function fixture(upstreamHandler) {
 const upstream=http.createServer(upstreamHandler);
 await new Promise(resolve=>upstream.listen(0,'127.0.0.1',resolve));
 const code="import http from 'node:http';import {handler} from './server.mjs';const server=http.createServer(handler);server.listen(0,'127.0.0.1',()=>console.log(server.address().port));process.on('SIGTERM',()=>{server.closeAllConnections();server.close(()=>process.exit(0));});";
 const child=spawn(process.execPath,['--input-type=module','-e',code],{env:{PATH:process.env.PATH,ROBOT_API_URL:`http://127.0.0.1:${upstream.address().port}`},stdio:['ignore','pipe','pipe']});
 let logs='';child.stderr.on('data',chunk=>logs+=chunk);
 const port=await new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>reject(new Error('Synthetic gateway startup deadline')),5000);
  child.stdout.once('data',chunk=>{clearTimeout(timer);resolve(Number(String(chunk).trim()));});
  child.once('error',error=>{clearTimeout(timer);reject(error);});
 });
 assert.ok(Number.isInteger(port)&&port>0);
 return {url:`http://127.0.0.1:${port}`,logs:()=>logs,async close(){const exited=new Promise(resolve=>child.once('exit',resolve));child.kill('SIGTERM');await exited;upstream.closeAllConnections();await new Promise(resolve=>upstream.close(resolve));}};
}

test('one delayed mutation acknowledgement survives the old four-second gateway deadline',async()=>{
 let writes=0,timer;
 const gateway=await fixture((req,res)=>{
  assert.equal(req.method,'POST');assert.equal(req.url,'/api/v1/reset');writes++;
  timer=setTimeout(()=>{res.writeHead(200,{'Content-Type':'application/json'});res.end('{"status":"reset","physical_actuation":false}');},4500);
 });
 try {
  const response=await fetch(gateway.url+'/api/v1/reset',{method:'POST',headers:{Origin:'http://synthetic.invalid','X-CSRF-Token':'synthetic-csrf'},body:'{"password":"synthetic-only"}'});
  assert.equal(response.status,200);assert.deepEqual(await response.json(),{status:'reset',physical_actuation:false});assert.equal(writes,1);assert.equal(gateway.logs(),'');
 }finally{clearTimeout(timer);await gateway.close();}
});

test('stalled response body fails boundedly without false success, session forwarding or replay',async()=>{
 let writes=0;
 const gateway=await fixture((req,res)=>{
  writes++;res.writeHead(200,{'Content-Type':'application/json','Set-Cookie':'robot_session=synthetic-private-marker; Path=/api/v1'});res.flushHeaders();res.write('{');
 });
 try {
  const start=performance.now();const response=await fetch(gateway.url+'/api/v1/reset',{method:'POST',body:'{"password":"synthetic-private-marker"}'});
  assert.equal(response.status,503);assert.equal(response.headers.get('cache-control'),'no-store');assert.equal(response.headers.getSetCookie().length,0);assert.equal(response.headers.get('x-onesa-gateway-error'),'upstream_timeout');assert.deepEqual(await response.json(),{detail:'Gateway unavailable'});
  assert.ok(performance.now()-start>=7500);assert.ok(performance.now()-start<10000);assert.equal(writes,1);
  const logs=gateway.logs();assert.match(logs,/"category":"upstream_timeout"/);assert.doesNotMatch(logs,/synthetic-private-marker|password|robot_session|https?:|\/api\/v1\//);
 }finally{await gateway.close();}
});

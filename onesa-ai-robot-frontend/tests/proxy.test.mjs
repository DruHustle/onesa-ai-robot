import {test} from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {spawn} from 'node:child_process';
import {setTimeout as sleep} from 'node:timers/promises';
test('proxy preserves auth boundaries, strips unrelated secrets and rejects open routes',async()=>{
 let received;
 const upstream=http.createServer((req,res)=>{received=req.headers;res.setHeader('Content-Type','application/json');res.setHeader('Set-Cookie',['robot_session=fixture; Path=/api/v1; HttpOnly','unrelated=secret']);res.end('{}');});
 await new Promise(resolve=>upstream.listen(0,'127.0.0.1',resolve));
 const child=spawn(process.execPath,['server.mjs'],{env:{...process.env,PORT:'3439',ROBOT_API_URL:`http://127.0.0.1:${upstream.address().port}`},stdio:'ignore'});
 try {
  let ready=false;for(let i=0;i<40;i++){try{ready=(await fetch('http://127.0.0.1:3439/')).ok;}catch{}if(ready)break;await sleep(50);}assert.ok(ready);
  const response=await fetch('http://127.0.0.1:3439/api/v1/status',{headers:{cookie:'robot_session=fixture; vercel-bypass=private','x-vercel-protection-bypass':'private','x-forwarded-for':'spoofed'}});
  assert.equal(response.status,200);assert.equal(received.cookie,'robot_session=fixture');assert.equal(received['x-vercel-protection-bypass'],undefined);assert.equal(received['x-forwarded-for'],undefined);assert.equal(response.headers.getSetCookie().length,1);
  assert.equal((await fetch('http://127.0.0.1:3439/api/v1/status?url=https://attacker.invalid')).status,404);
  assert.equal((await fetch('http://127.0.0.1:3439/api/v1/private')).status,404);
  assert.equal((await fetch('http://127.0.0.1:3439/api/v1/stop',{method:'POST',body:'x'.repeat(16385)})).status,413);
  assert.equal((await fetch('http://127.0.0.1:3439/.env')).status,404);
  assert.equal((await fetch('http://127.0.0.1:3439/')).headers.get('content-security-policy').includes("frame-ancestors 'none'"),true);
 } finally {child.kill('SIGTERM');await new Promise(resolve=>child.once('exit',resolve));await new Promise(resolve=>upstream.close(resolve));}
});

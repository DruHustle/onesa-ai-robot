import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {once} from 'node:events';
import {RobotClient} from '../public/client.js';

test('navigation cancellation aborts pending requests and a restored page can request again',async()=>{
 let observed;const received=new Promise(resolve=>observed=resolve);
 const server=http.createServer((request,response)=>{if(request.url==='/pending'){observed();return;}response.setHeader('Content-Type','application/json');response.end('{"stopped":true}');});
 server.listen(0,'127.0.0.1');await once(server,'listening');
 try{const client=new RobotClient();const origin=`http://127.0.0.1:${server.address().port}`;const pending=client.request(origin+'/pending');await received;client.cancelPending();await assert.rejects(pending,{name:'AbortError'});assert.deepEqual(await client.request(origin+'/restored'),{stopped:true});}
 finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});

test('a successful HTTP response with invalid JSON cannot masquerade as simulator state',async()=>{
 const server=http.createServer((request,response)=>response.end('<html>Gateway</html>'));server.listen(0,'127.0.0.1');await once(server,'listening');
 try{await assert.rejects(new RobotClient().request(`http://127.0.0.1:${server.address().port}`),/invalid response/);}
 finally{server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
});

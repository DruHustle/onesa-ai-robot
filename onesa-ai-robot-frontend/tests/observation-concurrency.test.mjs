import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';

const tick=()=>new Promise(resolve=>setImmediate(resolve));
const status={stopped:false,position_radians:0.1,active_task:null,sampled_at:1,deployment_environment:'local',capabilities:{edge_telemetry:'not_connected'}};
const tasks={tasks:[{id:'synthetic-unit-task',state:'completed',reason:'operator_approved',created:1,position:0.1}]};
function deferred(){let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};}

async function fixture(observationDelayMs=0){
 const source=(await readFile(new URL('../public/app.js',import.meta.url),'utf8')).replace("import {RobotClient} from './client.js';",'');
 const nodes=new Map(),windows=new Map(),pending={heartbeat:[],status:[],tasks:[]},calls={heartbeat:0,status:0,tasks:0,cancelPending:0};let restoredSession=null;
 const node=id=>{if(!nodes.has(id))nodes.set(id,{id,hidden:false,value:'synthetic-only',textContent:'',children:[],focus(){},addEventListener(){},replaceChildren(...children){this.children=children;},append(child){this.children.push(child);}});return nodes.get(id);};
 function request(operation,value){const result=deferred();pending[operation].push(result);calls[operation]++;if(observationDelayMs&&operation!=='heartbeat')setTimeout(()=>result.resolve(value),observationDelayMs);return result.promise;}
 class RobotClient{
  constructor(){this.pending=new AbortController();}
  me(){return restoredSession?Promise.resolve(restoredSession):Promise.reject({status:401});}
  heartbeat(){return request('heartbeat',{});}
  status(){return request('status',status);}
  tasks(){return request('tasks',tasks);}
  cancelPending(){calls.cancelPending++;this.pending.abort();this.pending=new AbortController();}
 }
 const context={RobotClient,document:{getElementById:node,querySelectorAll:()=>[],createElement:()=>({textContent:'',append(){}})},window:{addEventListener(event,handler){windows.set(event,handler);}},setInterval(){return 1;},clearInterval(){},setTimeout,AbortController,AbortSignal,Date,performance};
 node('history');vm.createContext(context);vm.runInContext(source,context);await tick();
 vm.runInContext("csrf='synthetic-session';client.csrf=csrf;byId('operator').hidden=false;byId('login-form').hidden=true;",context);
 return {calls,pending,nodes,windows,context,restoreSession(session){restoredSession=session;},refresh:()=>vm.runInContext('refresh()',context)};
}

test('an acknowledged heartbeat starts both observations without waiting for either read',async()=>{
 const f=await fixture();const refreshing=f.refresh();
 assert.equal(f.calls.heartbeat,1);assert.equal(f.calls.status,0);assert.equal(f.calls.tasks,0);
 f.pending.heartbeat[0].resolve({});await tick();
 assert.equal(f.calls.status,1);assert.equal(f.calls.tasks,1);
 f.pending.tasks[0].resolve(tasks);await tick();assert.equal(f.nodes.get('history').children.length,0);
 f.pending.status[0].resolve(status);await refreshing;
 assert.match(f.nodes.get('history').children[0].textContent,/completed/);
 assert.deepEqual(f.calls,{heartbeat:1,status:1,tasks:1,cancelPending:0});
});

test('controlled observation latency is paid once per refresh rather than once per read',async t=>{
 const f=await fixture(1200);const started=performance.now();const refreshing=f.refresh();f.pending.heartbeat[0].resolve({});await refreshing;
 const elapsed=Math.round(performance.now()-started);t.diagnostic('Controlled 1200ms status/tasks observation latency: '+elapsed+'ms total');
 assert.ok(elapsed<2000,'independent reads must not add their latency sequentially');
 assert.match(f.nodes.get('history').children[0].textContent,/completed/);
 assert.deepEqual(f.calls,{heartbeat:1,status:1,tasks:1,cancelPending:0});
});

test('a late unauthorized observation cannot revoke a replacement session',async()=>{
 const f=await fixture();const refreshing=f.refresh();f.pending.heartbeat[0].resolve({});await tick();
 f.pending.status[0].resolve(status);await tick();
 vm.runInContext("signedOut();generation++;csrf='replacement-synthetic-session';client.csrf=csrf;byId('operator').hidden=false;byId('login-form').hidden=true;notice('Replacement session');",f.context);
 f.pending.tasks[0].reject(Object.assign(new Error('Previous synthetic session'),{status:401}));await refreshing;
 assert.equal(f.nodes.get('operator').hidden,false);assert.equal(f.nodes.get('login-form').hidden,true);assert.equal(f.nodes.get('notice').textContent,'Replacement session');assert.equal(f.nodes.get('history').children.length,0);
});

test('navigation cancels the observation lifecycle and prevents a new polling request',async()=>{
 const f=await fixture();const refreshing=f.refresh();f.pending.heartbeat[0].resolve({});await tick();
 f.pending.status[0].resolve(status);await tick();
 f.windows.get('pagehide')();f.pending.tasks[0].reject(Object.assign(new Error('Synthetic navigation'),{name:'AbortError'}));await refreshing;await f.refresh();
 assert.equal(f.calls.cancelPending,1);assert.equal(f.calls.heartbeat,1);assert.equal(f.nodes.get('history').children.length,0);
});

test('a fast read failure retains one polling batch until its other read settles',async()=>{
 const f=await fixture();const refreshing=f.refresh();f.pending.heartbeat[0].resolve({});await tick();
 f.pending.status[0].reject(Object.assign(new Error('Synthetic read unavailable'),{status:503}));await tick();
 assert.match(f.nodes.get('connection').textContent,/Disconnected/);
 const duplicate=f.refresh();await tick();assert.equal(f.calls.heartbeat,1);assert.equal(f.calls.status,1);assert.equal(f.calls.tasks,1);
 f.pending.tasks[0].resolve(tasks);await refreshing;await duplicate;
 const next=f.refresh();assert.equal(f.calls.heartbeat,2);f.pending.heartbeat[1].resolve({});await tick();f.pending.status[1].resolve(status);f.pending.tasks[1].resolve(tasks);await next;
});

test('an obsolete polling batch cannot clear ownership of a restored-page batch',async()=>{
 const f=await fixture();const old=f.refresh();f.pending.heartbeat[0].resolve({});await tick();
 f.windows.get('pagehide')();f.restoreSession({csrf:'restored-synthetic-session'});f.windows.get('pageshow')({persisted:true});await tick();
 assert.equal(f.calls.heartbeat,2);f.pending.heartbeat[1].resolve({});await tick();assert.equal(f.calls.tasks,2);
 f.pending.status[0].resolve(status);f.pending.tasks[0].resolve(tasks);await old;
 const duplicate=f.refresh();await tick();assert.equal(f.calls.heartbeat,2);assert.equal(f.calls.status,2);assert.equal(f.calls.tasks,2);
 f.pending.status[1].resolve(status);f.pending.tasks[1].resolve(tasks);await tick();await duplicate;
 assert.equal(f.nodes.get('operator').hidden,false);assert.equal(f.nodes.get('login-form').hidden,true);
});

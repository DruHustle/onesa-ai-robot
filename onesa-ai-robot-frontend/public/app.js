import {RobotClient} from './client.js';
const client = new RobotClient();
const byId = id => document.getElementById(id);
let csrf = '', proposalId = '', timer, polling = false, generation=0, suspended=false;
const notice = text => { byId('notice').textContent = text; };

function signedOut() {generation++; clearInterval(timer);csrf='';client.csrf='';proposalId='';byId('operator').hidden=true;byId('login-form').hidden=false;byId('approval-form').hidden=true;byId('history').replaceChildren(); }
async function refresh() {
  if(suspended || polling || !csrf) return;
  polling=true;const current=generation;
  try {
    await client.heartbeat();
    if(suspended || current!==generation) return;
    const status=await client.status();
    if(current!==generation) return;
    byId('connection').textContent='Connected to software simulator';
    byId('stop-state').textContent=status.stopped?'Stopped — password-confirmed reset required':'Ready for a simulation proposal';
    byId('position').textContent=Number(status.position_radians).toFixed(4);
    byId('active').textContent=status.active_task || 'None';
    byId('sampled-at').textContent=Number.isFinite(status.sampled_at)?new Date(status.sampled_at*1000).toLocaleString(undefined,{timeZoneName:'short'}):'Unavailable · simulator API update required';
    byId('edge-state').textContent=status.capabilities.edge_telemetry==='simulation_connected'?'Synthetic edge telemetry received':'Disconnected · no fresh synthetic edge telemetry';
    byId('environment').textContent=status.deployment_environment==='local'?'DEVELOPMENT':['staging','production'].includes(status.deployment_environment)?status.deployment_environment.toUpperCase():'ENVIRONMENT UNAVAILABLE';
    byId('environment').hidden=false;
    const {tasks}=await client.tasks();
    if(current!==generation) return;
    byId('history').replaceChildren(...tasks.map(task=>{const li=document.createElement('li');li.textContent=`${task.state} · ${task.id} · ${task.reason} · ${new Date(task.created*1000).toLocaleString()} · ${Number(task.position).toFixed(4)} rad`;if(task.state==='running'){const button=document.createElement('button');button.textContent='Cancel running task';button.addEventListener('click',()=>run(()=>client.cancel(task.id),'Task cancelled; simulation stopped.'));li.append(button);}return li;}));
    if(!tasks.length){const li=document.createElement('li');li.textContent='No simulation tasks yet. Reset the stop state to create a proposal.';byId('history').append(li);}
  } catch(error) {if(current!==generation) return;byId('connection').textContent='Disconnected — telemetry is stale; the gateway watchdog stops running simulation tasks.';byId('position').textContent='Stale · latest response unavailable';if(error.status===401) signedOut();notice(error.message);}
  finally {polling=false;}
}
const busyForms=new WeakSet();
async function run(action, success) {
  if(suspended)return;
  const form=document.activeElement?.closest('form');
  if(form&&busyForms.has(form))return;
  const controls=form?[...form.querySelectorAll('button[type="submit"]')]:[];
  if(form){busyForms.add(form);form.setAttribute('aria-busy','true');controls.forEach(control=>control.disabled=true);}
  try {await action();if(suspended)return;notice(success);await refresh();}
  catch(error){if(suspended)return;if(error.status===401) signedOut();notice(error.message);}
  finally{if(form){busyForms.delete(form);form.removeAttribute('aria-busy');controls.forEach(control=>control.disabled=false);}}
}
byId('login-form').addEventListener('submit',event=>{event.preventDefault();const password=byId('password').value;byId('password').value='';run(async()=>{const session=await client.login({name:byId('name').value,password});generation++;csrf=session.csrf;client.csrf=csrf;byId('login-form').hidden=true;byId('operator').hidden=false;timer=setInterval(refresh,500);},'Signed in. Physical actuation remains disabled.');});
byId('reset-form').addEventListener('submit',event=>{event.preventDefault();const password=byId('reset-password').value;byId('reset-password').value='';run(()=>client.reset({password}),'Simulation stop reset.');});
byId('proposal-form').addEventListener('submit',event=>{event.preventDefault();run(async()=>{const data=await client.propose({command_id:crypto.randomUUID(),issued_at:Date.now()/1000,target_radians:Number(byId('target').value),duration_seconds:Number(byId('duration').value)});proposalId=data.id;byId('proposed-id').textContent=proposalId;byId('approval-form').hidden=false;byId('approve-password').focus();},'Proposal created. Confirm within 15 seconds.');});
byId('approval-form').addEventListener('submit',event=>{event.preventDefault();const password=byId('approve-password').value;byId('approve-password').value='';run(async()=>{await client.approve(proposalId,{password});byId('approval-form').hidden=true;proposalId='';},'Simulation running; heartbeat must remain connected.');});
byId('cancel').addEventListener('click',()=>run(async()=>{await client.cancel(proposalId);byId('approval-form').hidden=true;proposalId='';},'Proposal cancelled.'));
byId('stop').addEventListener('click',()=>run(()=>client.stop(),'Simulation stopped. Reset requires confirmation.'));
byId('logout').addEventListener('click',()=>run(async()=>{await client.logout();signedOut();},'Signed out; this session cannot authorize further tasks.'));
// No localStorage/sessionStorage, token URLs or persistence of operator credentials.

function restoreSession(){const current=++generation;return client.me().then(session=>{if(current!==generation)return;csrf=session.csrf;client.csrf=csrf;byId('login-form').hidden=true;byId('operator').hidden=false;timer=setInterval(refresh,500);return refresh();}).catch(error=>{if(current===generation&&error.status!==401&&error.name!=='AbortError')notice(error.message);});}
function suspendRequests(){suspended=true;generation++;clearInterval(timer);client.cancelPending();polling=false;}
window.addEventListener('beforeunload',suspendRequests);
window.addEventListener('pagehide',suspendRequests);
window.addEventListener('pageshow',event=>{if(event.persisted){suspended=false;restoreSession();}});
restoreSession();

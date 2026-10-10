import {RobotClient} from './client.js';
const client = new RobotClient();
const byId = id => document.getElementById(id);
let csrf = '', proposalId = '', timer, polling = false, generation=0;
const notice = text => { byId('notice').textContent = text; };

function signedOut() {generation++; clearInterval(timer);csrf='';client.csrf='';proposalId='';byId('operator').hidden=true;byId('login-form').hidden=false;byId('approval-form').hidden=true;byId('history').replaceChildren(); }
async function refresh() {
  if(polling || !csrf) return;
  polling=true;const current=generation;
  try {
    await client.heartbeat();
    const status=await client.status();
    if(current!==generation) return;
    byId('connection').textContent='Connected to software simulator';
    byId('stop-state').textContent=status.stopped?'Stopped — password-confirmed reset required':'Ready for a simulation proposal';
    byId('position').textContent=Number(status.position_radians).toFixed(4);
    byId('active').textContent=status.active_task || 'None';
    const {tasks}=await client.tasks();
    if(current!==generation) return;
    byId('history').replaceChildren(...tasks.map(task=>{const li=document.createElement('li');li.textContent=`${task.state} · ${task.id} · ${task.reason}`;if(task.state==='running'){const button=document.createElement('button');button.textContent='Cancel running task';button.addEventListener('click',()=>run(()=>client.cancel(task.id),'Task cancelled; simulation stopped.'));li.append(button);}return li;}));
  } catch(error) {byId('connection').textContent='Disconnected — telemetry is stale; the gateway watchdog stops running simulation tasks.';if(error.status===401) signedOut();notice(error.message);}
  finally {polling=false;}
}
async function run(action, success) {try {await action();notice(success);await refresh();}catch(error){if(error.status===401) signedOut();notice(error.message);}}
byId('login-form').addEventListener('submit',event=>{event.preventDefault();const password=byId('password').value;byId('password').value='';run(async()=>{const session=await client.login({name:byId('name').value,password});generation++;csrf=session.csrf;client.csrf=csrf;byId('login-form').hidden=true;byId('operator').hidden=false;timer=setInterval(refresh,500);},'Signed in. Physical actuation remains disabled.');});
byId('reset-form').addEventListener('submit',event=>{event.preventDefault();const password=byId('reset-password').value;byId('reset-password').value='';run(()=>client.reset({password}),'Simulation stop reset.');});
byId('proposal-form').addEventListener('submit',event=>{event.preventDefault();run(async()=>{const data=await client.propose({command_id:crypto.randomUUID(),issued_at:Date.now()/1000,target_radians:Number(byId('target').value),duration_seconds:Number(byId('duration').value)});proposalId=data.id;byId('proposed-id').textContent=proposalId;byId('approval-form').hidden=false;byId('approve-password').focus();},'Proposal created. Confirm within 15 seconds.');});
byId('approval-form').addEventListener('submit',event=>{event.preventDefault();const password=byId('approve-password').value;byId('approve-password').value='';run(async()=>{await client.approve(proposalId,{password});byId('approval-form').hidden=true;proposalId='';},'Simulation running; heartbeat must remain connected.');});
byId('cancel').addEventListener('click',()=>run(async()=>{await client.cancel(proposalId);byId('approval-form').hidden=true;proposalId='';},'Proposal cancelled.'));
byId('stop').addEventListener('click',()=>run(()=>client.stop(),'Simulation stopped. Reset requires confirmation.'));
byId('logout').addEventListener('click',()=>run(async()=>{await client.logout();signedOut();},'Signed out; this session cannot authorize further tasks.'));
// No localStorage/sessionStorage, token URLs or persistence of operator credentials.

client.me().then(session=>{generation++;csrf=session.csrf;client.csrf=csrf;byId('login-form').hidden=true;byId('operator').hidden=false;timer=setInterval(refresh,500);return refresh();}).catch(error=>{if(error.status!==401)notice(error.message);});

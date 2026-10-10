import type {paths,components} from './schema.js';
export type Proposal = components['schemas']['Proposal'];
export type Login = components['schemas']['Login'];
export type Confirmation = components['schemas']['Confirmation'];
export type SimulationStatus = components['schemas']['StatusResponse'];
export type TaskList = components['schemas']['TaskList'];
type ApiPath = keyof paths;
const routes = {
 me:'/api/v1/auth/me',login:'/api/v1/auth/login',logout:'/api/v1/auth/logout',status:'/api/v1/status',
 tasks:'/api/v1/tasks',heartbeat:'/api/v1/heartbeat',stop:'/api/v1/stop',reset:'/api/v1/reset',
 approve:'/api/v1/tasks/{task_id}/approve',cancel:'/api/v1/tasks/{task_id}/cancel'
} as const satisfies Record<string,ApiPath>;
export class RobotClient {
 csrf = '';
 async request<T>(path:string,body?:unknown):Promise<T> {
  const response=await fetch(path,{method:body===undefined?'GET':'POST',credentials:'same-origin',
   headers:body===undefined?{}:{'Content-Type':'application/json','X-CSRF-Token':this.csrf},
   ...(body===undefined?{}:{body:JSON.stringify(body)})});
  let data:unknown;
  try {data=await response.json();}catch{data={detail:'Gateway unavailable'};}
  if(!response.ok){const error=new Error(typeof (data as {detail?:unknown}).detail==='string'?(data as {detail:string}).detail:'Request rejected; check the configured safety limits.');Object.assign(error,{status:response.status});throw error;}
  return data as T;
 }
 me(){return this.request<components['schemas']['SessionResponse']>(routes.me);}
 login(value:Login){return this.request<components['schemas']['SessionResponse']>(routes.login,value);}
 logout(){return this.request<components['schemas']['ActionResponse']>(routes.logout,{});}
 status(){return this.request<SimulationStatus>(routes.status);}
 tasks(){return this.request<TaskList>(routes.tasks);}
 propose(value:Proposal){return this.request<components['schemas']['TaskResponse']>(routes.tasks,value);}
 approve(id:string,value:Confirmation){return this.request<components['schemas']['TaskResponse']>(routes.approve.replace('{task_id}',encodeURIComponent(id)),value);}
 cancel(id:string){return this.request<components['schemas']['ActionResponse']>(routes.cancel.replace('{task_id}',encodeURIComponent(id)),{});}
 heartbeat(){return this.request<components['schemas']['ActionResponse']>(routes.heartbeat,{});}
 stop(){return this.request<components['schemas']['ActionResponse']>(routes.stop,{});}
 reset(value:Confirmation){return this.request<components['schemas']['ActionResponse']>(routes.reset,value);}
}

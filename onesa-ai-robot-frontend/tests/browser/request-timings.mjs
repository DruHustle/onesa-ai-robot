// Restricted diagnostics contain fixed route labels, never headers, bodies or URLs.
const staticRoutes=new Set(['/','/console','/console/','/privacy','/app.js','/client.js','/theme.css','/onesa-foundation.css']);
const apiRoute=/^\/api\/v1\/(?:health|ready|status|tasks(?:\/[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}(?:\/(?:approve|cancel))?)?|auth\/(?:login|logout|me)|admin\/physical-operation(?:\/(?:allow|block))?|edge\/audit|heartbeat|stop|reset)$/;
export function createRequestTimings(baseURL,now=()=>performance.now()) {
 const origin=new URL(baseURL).origin,start=now(),active=new Map(),recent=[];
 const elapsed=()=>Math.max(0,Math.round(now()-start));
 const add=value=>{recent.push(value);if(recent.length>40)recent.shift();};
 function label(request){
  try{const url=new URL(request.url());if(url.origin!==origin)return null;
   if(staticRoutes.has(url.pathname))return url.pathname;
   if(!apiRoute.test(url.pathname))return null;
   return url.pathname.replace(/[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}/g,':task');
  }catch{return null;}
 }
 return {
  started(request){const route=label(request);if(!route)return;const method=['GET','POST','HEAD'].includes(request.method())?request.method():'OTHER';const value={route,method,started_ms:elapsed()};active.set(request,value);if(active.size>40)active.delete(active.keys().next().value);add({...value,phase:'started'});},
  headers(response){const value=active.get(response.request());if(value)add({...value,phase:'headers',status:response.status(),elapsed_ms:elapsed()-value.started_ms});},
  finished(request){const value=active.get(request);if(value){add({...value,phase:'complete',elapsed_ms:elapsed()-value.started_ms});active.delete(request);}},
  failed(request){const value=active.get(request);if(value){add({...value,phase:'transport_failed',elapsed_ms:elapsed()-value.started_ms});active.delete(request);}},
  lifecycle(phase){if(['domcontentloaded','load'].includes(phase))add({phase,elapsed_ms:elapsed()});},
  snapshot(){return {recent:recent.map(x=>({...x})),pending:[...active.values()].map(x=>({...x,elapsed_ms:elapsed()-x.started_ms}))};},
 };
}
export function observeRequestTimings(page,baseURL){
 const recorder=createRequestTimings(baseURL);
 page.on('request',q=>recorder.started(q));page.on('response',q=>recorder.headers(q));
 page.on('requestfinished',q=>recorder.finished(q));page.on('requestfailed',q=>recorder.failed(q));
 page.on('domcontentloaded',()=>recorder.lifecycle('domcontentloaded'));page.on('load',()=>recorder.lifecycle('load'));
 return recorder;
}

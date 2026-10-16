/** Independent static operator frontend with a fixed, server-only API proxy. */
import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { resolve, extname } from 'node:path';
import {fileURLToPath} from 'node:url';
const root = resolve(import.meta.dirname, 'dist');
const port = Number(process.env.PORT || 3431);
const upstream = new URL(process.env.ROBOT_API_URL || 'http://127.0.0.1:8431');
if (!['http:', 'https:'].includes(upstream.protocol) || upstream.username || upstream.password || upstream.pathname !== '/' || upstream.search || upstream.hash) throw new Error('ROBOT_API_URL must be a credential-free HTTP(S) origin');
if (upstream.protocol === 'http:' && !['127.0.0.1', 'localhost', 'backend'].includes(upstream.hostname)) throw new Error('Remote gateway requires TLS');
const routes = /^\/api\/v1\/(edge\/audit|health|ready|auth\/(login|logout|me)|admin\/physical-operation(?:\/(allow|block))?|status|tasks(?:\/[a-f0-9-]{36}\/(approve|cancel))?|heartbeat|stop|reset)$/;
const security = {
  'Content-Security-Policy': "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
  'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=()', 'X-Frame-Options': 'DENY'
};
export async function handler(req, res) {
  for (const [key,value] of Object.entries(security)) res.setHeader(key,value);
  try {
    const url = new URL(req.url || '/', 'http://frontend.invalid');
    if (url.pathname.startsWith('/api/')) {
      res.setHeader('Cache-Control','no-store');
      if (!routes.test(url.pathname) || url.search || !['GET','POST'].includes(req.method)) {res.writeHead(404).end(); return;}
      const headers = {accept:'application/json'};
      for (const name of ['origin','content-type','x-csrf-token']) if (req.headers[name]) headers[name] = req.headers[name];
      const cookie = (req.headers.cookie || '').split(';').map(x=>x.trim()).filter(x=>/^robot_session=/.test(x)).join('; ');
      if (cookie) headers.cookie = cookie;
      const chunks=[]; let size=0;
      for await (const chunk of req) { size+=chunk.length; if(size>16384) {res.writeHead(413).end();return;} chunks.push(chunk); }
      const response = await fetch(new URL(url.pathname,upstream), {method:req.method,headers,
        // A journal write plus its bounded read-only confirmation can take six
        // seconds. Leave two seconds for ingress, below the client's ten-second
        // deadline. Never retry a mutation after an uncertain acknowledgement.
        ...(req.method==='POST'?{body:Buffer.concat(chunks)}:{}), redirect:'manual',signal:AbortSignal.timeout(8000)});
      if (response.status >= 300 && response.status < 400) {res.writeHead(502).end();return;}
      const body=Buffer.from(await response.arrayBuffer());
      const cookies=response.headers.getSetCookie().filter(x=>/^robot_session=/.test(x));
      if(cookies.length) res.setHeader('Set-Cookie',cookies);
      res.setHeader('Content-Type',response.headers.get('content-type') || 'application/json');
      res.writeHead(response.status).end(body);
      return;
    }
    if (!['GET','HEAD'].includes(req.method)) {res.writeHead(405).end();return;}
    const files = new Map([['/','index.html'],['/index.html','index.html'],['/console','console.html'],['/console/','console.html'],['/console.html','console.html'],['/privacy','privacy.html'],['/privacy/','privacy.html'],['/privacy.html','privacy.html'],['/onesa-foundation.css','onesa-foundation.css'],['/theme.css','theme.css'],['/app.js','app.js'],['/client.js','client.js'],['/brand/onesa-orbit.png','brand/onesa-orbit.png'],['/robots.txt','robots.txt']]);
    files.set('/favicon.ico','favicon.ico');
    for(const width of [640,1280])files.set('/images/robot-concept-'+width+'.webp','images/robot-concept-'+width+'.webp');
    for(const file of ['onesa-robot.svg','onesa-robot.ico','onesa-robot-16.png','onesa-robot-32.png','onesa-robot-64.png','onesa-robot-180.png'])files.set('/brand/icons/v1/'+file,'brand/icons/v1/'+file);
    const file = files.get(url.pathname);
    if (!file) {res.writeHead(404).end();return;}
    const body=await readFile(resolve(root,file));
    const type={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.png':'image/png','.webp':'image/webp','.txt':'text/plain; charset=utf-8','.svg':'image/svg+xml','.ico':'image/vnd.microsoft.icon'}[extname(file)];
    res.setHeader('Content-Type',type);res.setHeader('Cache-Control','no-cache');
    res.writeHead(200).end(req.method==='HEAD'?undefined:body);
  } catch (error) {
    const codes=new Set(['ECONNRESET','ECONNREFUSED','ENOTFOUND','EAI_AGAIN','ETIMEDOUT','UND_ERR_CONNECT_TIMEOUT','UND_ERR_SOCKET']);
    const category=error?.name==='TimeoutError'?'upstream_timeout':codes.has(error?.cause?.code)?error.cause.code:'gateway_unavailable';
    // Fixed categories only: no URL, operator, cookie, password or error message.
    console.error(JSON.stringify({event:'robot_gateway_failure',category}));
    if (!res.headersSent) res.writeHead(503,{'Content-Type':'application/json','Cache-Control':'no-store','X-Onesa-Gateway-Error':category});
    res.end('{"detail":"Gateway unavailable"}');
  }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
const server = http.createServer(handler);
server.requestTimeout=5000; server.headersTimeout=5000; server.maxConnections=128;
server.listen(port,'0.0.0.0');
for(const signal of ['SIGTERM','SIGINT']) process.on(signal,()=>{server.close(()=>process.exit(0));setTimeout(()=>process.exit(1),5000).unref();});

}

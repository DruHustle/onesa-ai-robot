import {cp,mkdir,readFile,rm,writeFile} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
for(const path of ['server.mjs','public/app.js']) {const result=spawnSync(process.execPath,['--check',path],{stdio:'inherit'});if(result.status)process.exit(result.status);}
const pages=await Promise.all(['index.html','console.html'].map(file=>readFile('public/'+file,'utf8')));
const html=pages.join('\n');
const company=JSON.parse(await readFile('public/company.json','utf8'));
for(const name of ['legalName','address','email','telephone','mailHref','telephoneHref'])if(typeof company[name]!=='string'||!html.includes(company[name]))throw new Error('Company footer differs from the approved snapshot: '+name);
for(const asset of ['app.js','onesa-foundation.css','theme.css','brand/onesa-orbit.png']){await readFile('public/'+asset);if(!html.includes('/'+asset))throw new Error('Missing linked asset: '+asset);}
const manifest=JSON.parse(await readFile('design-system.consumer.json','utf8'));
const {createHash}=await import('node:crypto');
if(createHash('sha256').update(await readFile('public/onesa-foundation.css')).digest('hex')!==manifest.sha256)throw new Error('Shared foundation differs from pinned owner artifact');
const compile=spawnSync(process.execPath,['node_modules/typescript/bin/tsc','--noEmit','false','--outDir','dist-types'],{stdio:'inherit'});if(compile.status)process.exit(compile.status);
await cp('dist-types/client.js','public/client.js');
await rm('dist',{recursive:true,force:true});await mkdir('dist',{recursive:true});await cp('public','dist',{recursive:true});
const registryBytes=await readFile('onesa-applications.json');
if(createHash('sha256').update(registryBytes).digest('hex')!==manifest.applications.sha256)throw new Error('Application registry differs from pinned owner artifact');
const registry=JSON.parse(registryBytes);
const navigation=registry.applications.filter(application=>application.id!=='robot').map(application=>`<a href="${application.href}">${application.label} ↗</a>`).join('');
for(const file of ['index.html','console.html']){const source=await readFile('dist/'+file,'utf8');await writeFile('dist/'+file,source.replace(/(<nav[^>]*data-onesa-applications[^>]*>)[\s\S]*?(<\/nav>)/g,`$1${navigation}$2`));}
console.log('Built independent static simulation interface. Gateway hosting remains separate.');

import {cp,mkdir,readFile,rm} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
for(const path of ['server.mjs','public/app.js']) {const result=spawnSync(process.execPath,['--check',path],{stdio:'inherit'});if(result.status)process.exit(result.status);}
const html=await readFile('public/index.html','utf8');
for(const asset of ['app.js','theme.css','brand/onesa-orbit.png']){await readFile('public/'+asset);if(!html.includes('/'+asset))throw new Error('Missing linked asset: '+asset);}
const compile=spawnSync(process.execPath,['node_modules/typescript/bin/tsc','--noEmit','false','--outDir','dist-types'],{stdio:'inherit'});if(compile.status)process.exit(compile.status);
await cp('dist-types/client.js','public/client.js');
await rm('dist',{recursive:true,force:true});await mkdir('dist',{recursive:true});await cp('public','dist',{recursive:true});
console.log('Built independent static simulation interface. Gateway hosting remains separate.');

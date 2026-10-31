import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { runInNewContext } from 'node:vm';

const code = readFileSync(new URL('../public/sw.js', import.meta.url), 'utf8');
function worker(fetcher = async (_request: unknown) => new Response('online'), clients: Array<{postMessage:(data:any,ports:any[])=>void}> = []) {
  let activations=0;
  class TestChannel {
    port1: {onmessage:((event:any)=>void)|null;close:()=>void} = {onmessage:null,close:()=>{}};
    port2 = {postMessage:(data:any)=>queueMicrotask(()=>this.port1.onmessage?.({data}))};
  }
  const handlers: Record<string, (event: any) => void> = {};
  const writes: string[][] = [];
  const cache = {
    addAll: async (paths: string[]) => { writes.push([...paths]); },
    match: async (path: unknown) => path === '/offline.html' ? new Response('public offline') : undefined,
  };
  const context = { MessageChannel:TestChannel, setTimeout:(fn:()=>void,ms:number)=>setTimeout(fn,Math.min(ms,10)), clearTimeout, self: { clients:{matchAll:async()=>clients}, skipWaiting:async()=>{activations+=1;}, location: {origin:'https://example.test'}, addEventListener: (name: string, listener: (event:any)=>void) => { handlers[name] = listener; } },
    caches: { open: async () => cache, keys: async () => [], delete: async () => true }, URL, Response, fetch: fetcher };
  runInNewContext(code, context);
  return { handlers, writes, activations:()=>activations };
}

test('service worker never intercepts API, RSC, third-party fetches or mutations', () => {
  const {handlers} = worker();
  for (const [method,path,mode] of [['POST','/api/v1/orders','cors'],['GET','/api/v1/messages','cors'],['GET','/api/v2/messages','cors'],['GET','/api/v2/document','cors'],['GET','/api/v2/document/openapi.json','cors'],['GET','/version.json','cors'],['GET','/?_rsc=private','cors'],['GET','/admin/','cors'],['GET','/icons/icon-192.png?private=1','cors'],['GET','https://other.test/icons/icon-192.png','cors']]) {
    let intercepted = false;
    handlers.fetch({request:{method,url:new URL(path,'https://example.test').href,mode},respondWith:()=>{intercepted=true;}});
    assert.equal(intercepted,false,`${method} ${path}`);
  }
});

test('installation persists only the exact public fallback and icon allowlist', async () => {
  const {handlers,writes} = worker();
  let pending:Promise<unknown> = Promise.resolve();
  handlers.install({waitUntil:(p:Promise<unknown>)=>{pending=p;}});
  await pending;
  assert.deepEqual(writes[0], ['/offline.html','/icons/icon-192.png','/icons/icon-512.png','/icons/maskable-512.png']);
});

test('failed private navigation returns anonymous fallback without persisting private HTML', async () => {
  const {handlers,writes} = worker(async()=>{throw new Error('offline');});
  let response:Promise<Response> = Promise.resolve(new Response());
  handlers.fetch({request:{method:'GET',url:'https://example.test/history',mode:'navigate'},respondWith:(p:Promise<Response>)=>{response=p;}});
  assert.equal(await(await response).text(),'public offline');
  assert.equal(writes.length,0);
});


test('waiting update cannot activate while another tab is dirty or does not acknowledge', async () => {
  for(const state of [false, null]) {
    const w=worker(undefined,[{postMessage:(_data,ports)=>ports[0].postMessage({idle:true})},{postMessage:(_data,ports)=>{if(state!==null)ports[0].postMessage({idle:state});}}]);
    let pending:Promise<unknown>=Promise.resolve(); let blocked=false;
    w.handlers.message({data:{type:'ACTIVATE_APPROVED_UPDATE'},source:{postMessage:()=>{blocked=true;}},waitUntil:(p:Promise<unknown>)=>{pending=p;}});
    await pending;
    assert.equal(w.activations(),0);
    assert.equal(blocked,true);
  }
});

test('waiting update activates only after every tab acknowledges idle', async () => {
  const w=worker(undefined,[{postMessage:(_data,ports)=>ports[0].postMessage({idle:true})},{postMessage:(_data,ports)=>ports[0].postMessage({idle:true})}]);
  let pending:Promise<unknown>=Promise.resolve();
  w.handlers.message({data:{type:'ACTIVATE_APPROVED_UPDATE'},waitUntil:(p:Promise<unknown>)=>{pending=p;}});
  await pending;
  assert.equal(w.activations(),1);
});

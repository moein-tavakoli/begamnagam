import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { runInNewContext } from 'node:vm';

const code = readFileSync(new URL('../public/sw.js', import.meta.url), 'utf8');
function worker(fetcher = async (_request: unknown) => new Response('online')) {
  const handlers: Record<string, (event: any) => void> = {};
  const writes: string[][] = [];
  const cache = {
    addAll: async (paths: string[]) => { writes.push([...paths]); },
    match: async (path: unknown) => path === '/offline.html' ? new Response('public offline') : undefined,
  };
  const context = { self: { location: {origin:'https://example.test'}, addEventListener: (name: string, listener: (event:any)=>void) => { handlers[name] = listener; } },
    caches: { open: async () => cache, keys: async () => [], delete: async () => true }, URL, Response, fetch: fetcher };
  runInNewContext(code, context);
  return { handlers, writes };
}

test('service worker never intercepts API, RSC, third-party fetches or mutations', () => {
  const {handlers} = worker();
  for (const [method,path,mode] of [['POST','/api/v1/orders','cors'],['GET','/api/v1/messages','cors'],['GET','/?_rsc=private','cors'],['GET','/admin/','cors'],['GET','/icons/icon-192.png?private=1','cors'],['GET','https://other.test/icons/icon-192.png','cors']]) {
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

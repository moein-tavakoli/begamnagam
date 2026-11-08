import assert from 'node:assert/strict';
import { test } from 'node:test';
import * as monitoring from '../lib/monitoring.ts';
import { managementNavigation, managementShowsBalances } from '../lib/management.ts';

test('monitoring is restricted to operations permission and never shows balance cards',()=>{
  assert.ok(!managementNavigation({authenticated:true,permissions:[]}).some(x=>x.key==='monitoring'));
  assert.ok(managementNavigation({authenticated:true,permissions:['view_operations']}).some(x=>x.key==='monitoring'));
  assert.equal(managementShowsBalances('monitoring',['view_operations']),false);
});
test('refresh settings accept only supported periods with default thirty seconds',()=>{
  for(const value of [null,'', 'bad','0','-30','31','Infinity'])assert.equal(monitoring.monitoringInterval(value),30);
  for(const value of [30,60,120,300])assert.equal(monitoring.monitoringInterval(String(value)),value);
});
test('polling serializes requests, aborts on pause, resumes and stops without late updates',async()=>{
  let active=true, calls=0, signals:AbortSignal[]=[], delivered:number[]=[], queued:{fn:()=>void;ms:number}[]=[];
  let resolve:((x:number)=>void)|undefined;
  const poll=monitoring.startMonitoringPoll<number>({
    request:signal=>{calls++;signals.push(signal);return new Promise(r=>{resolve=r;});},
    active:()=>active, intervalMs:30000, onData:value=>delivered.push(value),onError:()=>false,
    schedule:(fn,ms)=>{queued.push({fn,ms});return fn;},cancel:id=>{queued=queued.filter(x=>x.fn!==id);},
  });
  poll.refresh();poll.refresh();assert.equal(calls,1);
  resolve!(7);await new Promise(r=>setImmediate(r));assert.deepEqual(delivered,[7]);assert.equal(queued[0].ms,30000);
  active=false;poll.pause();assert.equal(queued.length,0);poll.refresh();assert.equal(calls,1);
  active=true;poll.refresh();assert.equal(calls,2);poll.pause();assert.equal(signals[1].aborted,true);
  resolve!(8);await new Promise(r=>setImmediate(r));assert.deepEqual(delivered,[7]);
  queued.shift()!.fn();assert.equal(calls,3);poll.stop();resolve!(9);await new Promise(r=>setImmediate(r));assert.deepEqual(delivered,[7]);assert.equal(queued.length,0);
});
test('failed refresh preserves last data while fatal auth failure stops polling',async()=>{
  let calls=0, last=0, errors=0, queued:{fn:()=>void;ms:number}[]=[];
  const poll=monitoring.startMonitoringPoll<number>({request:async()=>{if(++calls===1)return 3;throw Error('failed');},active:()=>true,intervalMs:60000,onData:n=>{last=n;},onError:()=>++errors===2,
    schedule:(fn,ms)=>{queued.push({fn,ms});return fn;},cancel:id=>{queued=queued.filter(x=>x.fn!==id);}});
  await new Promise(r=>setImmediate(r));assert.equal(last,3);queued.shift()!.fn();await new Promise(r=>setImmediate(r));assert.equal(last,3);assert.equal(errors,1);
  queued.shift()!.fn();await new Promise(r=>setImmediate(r));assert.equal(errors,2);assert.equal(queued.length,0);poll.refresh();assert.equal(calls,3);poll.stop();
});
test('alert measurements keep queue age in time units and budget flag is not an event count',()=>{
  assert.equal(monitoring.monitoringAlertValue('queue_age',980),'۱۶ دقیقه انتظار');
  assert.equal(monitoring.monitoringAlertValue('delivery_unknown',3),'۳ مورد');
  assert.equal(monitoring.monitoringAlertValue('budget_80_percent',1),'بررسی بودجه');
});

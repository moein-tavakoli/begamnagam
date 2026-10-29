import test from 'node:test';
import assert from 'node:assert/strict';
import { mergeSupportMessages, pendingIsConfirmed, supportAccessLost, supportLauncherBottom, type SupportMessage } from '../lib/support.ts';
const message=(id:string,sequence:number,text='متن'):SupportMessage=>({id,sequence,text,role:'customer',redacted:false,created_at:'2026-10-28T10:00:00Z'});
test('poll and history pages merge in server order and retention replaces an existing body',()=>{
  const messages=mergeSupportMessages([message('b',2),message('c',3)], [message('a',1),{...message('b',2,''),redacted:true}]);
  assert.deepEqual(messages.map(m=>m.sequence),[1,2,3]);assert.equal(messages[1].text,'');assert.equal(messages[1].redacted,true);
  assert.equal(mergeSupportMessages(messages,[message('c',3)]).length,3);
});
test('an uncertain send is acknowledged only by its own server-returned client key',()=>{
  const pending={text:'سلام',key:'same-message-key',replyTo:0};
  assert(!pendingIsConfirmed(pending,[{...message('a',1,'سلام'),client_key:'different-key'}]));
  assert(pendingIsConfirmed(pending,[{...message('b',2),client_key:'same-message-key'}]));
  assert(!pendingIsConfirmed(null,[]));
});
test('lost staff or product access clears the private conversation',()=>{
  for(const code of ['authentication_required','management_login_required','forbidden'])assert(supportAccessLost({code}));
  for(const code of ['network_error','rate_limited','invalid_support_text'])assert(!supportAccessLost({code}));
});

test('floating support clears bottom controls and leaves distant inline buttons alone',()=>{
  const button={left:12,right:60,height:48};
  assert.equal(supportLauncherBottom(900,button,[{left:12,right:363,top:812,bottom:888}]),100);
  assert.equal(supportLauncherBottom(900,button,[{left:0,right:375,top:833,bottom:900}]),79);
  assert.equal(supportLauncherBottom(900,button,[{left:20,right:350,top:400,bottom:455}]),20);
  assert.equal(supportLauncherBottom(900,button,[{left:390,right:1040,top:812,bottom:888}]),20);
});

export type SupportThreadData = {
  id: string; status: 'open'|'closed'; last_sequence: number; last_customer_sequence: number;
  answered_customer_sequence: number; staff_read_sequence: number; customer_read_sequence: number;
  needs_reply: boolean; updated_at: string; closed_at?: string|null;
  account_id?: number; phone_masked?: string; unread_count?: number;
};
export type SupportMessage = { id:string; sequence:number; role:'customer'|'staff'; text:string; created_at:string; redacted:boolean; client_key?:string };
export type SupportPage = { thread:SupportThreadData|null; messages:SupportMessage[]; has_older:boolean; before_cursor:number|null; staff_online:boolean };
export type SupportPending = { text:string; key:string; replyTo:number };
export const supportAccessLost = (error: unknown) => !!error && typeof error === 'object' && 'code' in error && ['authentication_required','management_login_required','forbidden'].includes(String(error.code));
export function mergeSupportMessages(previous:SupportMessage[],incoming:SupportMessage[]) {
  const records=new Map(previous.map(message=>[message.id,message]));
  for(const message of incoming)records.set(message.id,message);
  return [...records.values()].sort((a,b)=>a.sequence-b.sequence);
}
export const pendingIsConfirmed = (pending:SupportPending|null,messages:SupportMessage[]) => !!pending && messages.some(message=>message.client_key===pending.key);
export function supportTime(value:string){return new Intl.DateTimeFormat('fa-IR',{hour:'2-digit',minute:'2-digit',timeZone:'Asia/Tehran'}).format(new Date(value));}
export function supportDay(value:string){return new Intl.DateTimeFormat('fa-IR',{day:'numeric',month:'long',timeZone:'Asia/Tehran'}).format(new Date(value));}

export type SupportDraftState = { draft:string; pending:SupportPending|null };
export type SupportWorkspaceMemory = { thread:SupportThreadData|null; composer:SupportDraftState };

export function supportLauncherBottom(height:number,button:{left:number;right:number;height:number},obstacles:{left:number;right:number;top:number;bottom:number}[]) {
  let offset=20;
  for(const rect of [...obstacles].sort((a,b)=>b.top-a.top)){
    if(rect.right<=rect.left || rect.bottom<=rect.top)continue;
    const bottom=height-offset,top=bottom-button.height;
    if(rect.left<button.right && rect.right>button.left && rect.top<bottom+12 && rect.bottom>top-12)
      offset=Math.max(offset,height-rect.top+12);
  }
  return Math.min(Math.round(offset),Math.max(20,height-80));
}

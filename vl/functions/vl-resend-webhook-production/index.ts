import "jsr:@supabase/functions-js@2/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import { Webhook } from "npm:svix@1.69.0";

const URL=Deno.env.get("SUPABASE_URL")!;
const KEY=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const SECRET=(Deno.env.get("RESEND_PRODUCTION_WEBHOOK_SECRET")||"").trim();
const sb=createClient(URL,KEY,{auth:{persistSession:false}});
const J=(b:unknown,s=200)=>new Response(JSON.stringify(b),{
  status:s,headers:{"content-type":"application/json","cache-control":"no-store"}
});
async function sha256(t:string){
  const d=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(t));
  return [...new Uint8Array(d)].map(x=>x.toString(16).padStart(2,"0")).join("");
}
function norm(t:string){
  if(t==="email.delivered")return "delivered";
  if(t==="email.bounced")return "bounced";
  if(t==="email.failed")return "failed";
  if(t==="email.sent")return "sent";
  return null;
}

Deno.serve(async req=>{
  if(req.method!=="POST")return J({error:"POST required"},405);
  if(!SECRET)return J({error:"RESEND_PRODUCTION_WEBHOOK_SECRET not configured",blocked:true},503);

  const raw=await req.text();
  const headers={
    "svix-id":req.headers.get("svix-id")||"",
    "svix-timestamp":req.headers.get("svix-timestamp")||"",
    "svix-signature":req.headers.get("svix-signature")||""
  };

  let event:any;
  try{event=new Webhook(SECRET).verify(raw,headers)}
  catch{return J({error:"invalid webhook signature"},401)}

  const id=headers["svix-id"]||String(event?.id||"");
  if(!id)return J({error:"missing event id",blocked:true},400);

  const type=String(event?.type||"");
  const messageId=String(event?.data?.email_id||event?.data?.id||"");
  const status=norm(type);
  const hash=await sha256(raw);

  const {data,error}=await sb.rpc("vl_apply_resend_production_webhook",{
    p_event_key:`resend-prod:${id}`,
    p_provider_message_id:messageId,
    p_event_type:type,
    p_status:status,
    p_payload_sha256:hash
  });
  if(error)return J({error:"production webhook processing failed"},500);
  return J({ok:true,...data});
});

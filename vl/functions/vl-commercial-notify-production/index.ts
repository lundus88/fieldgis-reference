import "jsr:@supabase/functions-js@2/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

const URL=Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const ANON_KEY=Deno.env.get("SUPABASE_ANON_KEY")||Deno.env.get("SUPABASE_PUBLISHABLE_KEY")||"";
const API_KEY=(Deno.env.get("RESEND_PRODUCTION_API_KEY")||"").trim();
const FROM=(Deno.env.get("RESEND_PRODUCTION_FROM")||"").trim();
const sb=createClient(URL,SERVICE_KEY,{auth:{persistSession:false}});
const enc=new TextEncoder();

const J=(b:unknown,s=200)=>new Response(JSON.stringify(b),{
  status:s,
  headers:{"content-type":"application/json","cache-control":"no-store"}
});

async function sha256(t:string){
  const d=await crypto.subtle.digest("SHA-256",enc.encode(t));
  return [...new Uint8Array(d)].map(x=>x.toString(16).padStart(2,"0")).join("");
}
function jwtClaim(token:string,key:string){
  try{
    const p=token.split(".")[1].replace(/-/g,"+").replace(/_/g,"/");
    const j=JSON.parse(atob(p+"=".repeat((4-p.length%4)%4)));
    return j?.[key]??null;
  }catch{return null}
}
async function operator(request:Request){
  const auth=request.headers.get("authorization")||"";
  if(!auth.startsWith("Bearer "))return null;
  const token=auth.slice(7);
  const uc=createClient(URL,ANON_KEY,{
    global:{headers:{Authorization:auth}},
    auth:{persistSession:false}
  });
  const {data:{user},error}=await uc.auth.getUser();
  if(error||!user)return null;
  if(jwtClaim(token,"aal")!=="aal2")return {error:"aal2_required"};
  const {data:roles,error:roleErr}=await sb.from("project_members")
    .select("role").eq("user_id",user.id).in("role",["owner","admin"]).limit(1);
  if(roleErr||!roles?.length)return {error:"owner_admin_required"};
  return {user};
}

function money(minor:number){return `RM ${(minor/100).toFixed(2)}`;}
function template(kind:string,order:any){
  const ref=String(order.merchant_reference||"");
  const amount=money(Number(order.amount_minor||0));
  if(kind==="payment_confirmed"){
    return {
      subject:`Payment confirmed — ${ref}`,
      html:`<h1>Payment confirmed</h1><p>We received your payment of <strong>${amount}</strong>.</p><p>Order reference: <strong>${ref}</strong></p><p>Fulfilment is handled as a separate controlled step.</p>`
    };
  }
  if(kind==="order_fulfilled"){
    const receipt=String(order.metadata?.receipt_reference||"");
    return {
      subject:`Order fulfilled — ${ref}`,
      html:`<h1>Order fulfilled</h1><p>Your order <strong>${ref}</strong> has been marked fulfilled.</p>${receipt?`<p>Receipt reference: <strong>${receipt}</strong></p>`:""}<p>Please contact support if anything is incomplete.</p>`
    };
  }
  if(kind==="order_closed"){
    return {
      subject:`Order completed — ${ref}`,
      html:`<h1>Order completed</h1><p>Order <strong>${ref}</strong> has been completed and closed.</p><p>Thank you for working with LUNDUS DIGITAL SYSTEMS.</p>`
    };
  }
  return null;
}

Deno.serve(async req=>{
  if(req.method!=="POST")return J({error:"POST required"},405);
  if(!API_KEY||!FROM)return J({error:"Resend production configuration missing",blocked:true},503);

  const op=await operator(req);
  if(!op)return J({error:"authenticated operator required"},401);
  if("error" in op)return J({error:op.error},403);

  const {data:readiness,error:readyErr}=await sb.rpc("get_vrs_notification_production_readiness");
  if(readyErr||!readiness?.production_send_allowed||readiness?.adapter_status!=="active"){
    return J({error:"production notification adapter not ready",blocked:true},503);
  }

  const body=await req.json().catch(()=>({}));
  const orderId=String(body.order_id||"").trim();
  const kind=String(body.template_key||"").trim();
  if(!orderId||!["payment_confirmed","order_fulfilled","order_closed"].includes(kind)){
    return J({error:"valid order_id and template_key required"},400);
  }

  const {data:order,error:orderErr}=await sb.schema("private").from("payment_production_orders")
    .select("id,created_by,merchant_reference,amount_minor,currency,environment,purpose,status,fulfillment_state,metadata")
    .eq("id",orderId).maybeSingle();
  if(orderErr||!order)return J({error:"commercial order not found"},404);
  if(order.environment!=="production"||order.purpose!=="commercial_order"){
    return J({error:"production commercial order required",blocked:true},409);
  }
  if(kind==="payment_confirmed"&&order.status!=="paid")return J({error:"paid order required",blocked:true},409);
  if(kind==="order_fulfilled"&&order.fulfillment_state!=="fulfilled")return J({error:"fulfilled order required",blocked:true},409);
  if(kind==="order_closed"&&order.metadata?.commercial_closed!==true)return J({error:"closed order required",blocked:true},409);
  if(!order.created_by)return J({error:"customer identity missing",blocked:true},409);

  const {data:userData,error:userErr}=await sb.auth.admin.getUserById(order.created_by);
  const to=String(userData?.user?.email||"").trim().toLowerCase();
  if(userErr||!to)return J({error:"customer email unavailable",blocked:true},409);

  const rendered=template(kind,order);
  if(!rendered)return J({error:"template unavailable"},400);

  const idem=`lds-commercial:${order.id}:${kind}`;
  const response=await fetch("https://api.resend.com/emails",{
    method:"POST",
    headers:{
      Authorization:`Bearer ${API_KEY}`,
      "content-type":"application/json",
      "Idempotency-Key":idem
    },
    body:JSON.stringify({from:FROM,to:[to],subject:rendered.subject,html:rendered.html}),
    redirect:"error"
  });
  const text=await response.text();
  let data:any;try{data=JSON.parse(text)}catch{data={}};
  if(!response.ok||!data?.id)return J({error:"Resend production send failed",provider_status:response.status},502);

  const recipientHash=await sha256(to);
  const {data:record,error:recordErr}=await sb.rpc("vl_record_commercial_notification_send",{
    p_order_id:order.id,
    p_template_key:kind,
    p_recipient_hash:recipientHash,
    p_subject:rendered.subject,
    p_provider_message_id:String(data.id),
    p_idempotency_key:idem,
    p_created_by:op.user.id
  });
  if(recordErr){
    return J({
      error:"provider sent but notification evidence recording failed",
      provider_message_id:String(data.id),
      idempotency_key:idem,
      manual_review:true
    },500);
  }

  return J({
    ok:true,
    environment:"production",
    template_key:kind,
    provider_message_id:String(data.id),
    idempotency_key:idem,
    recipient_pii_stored:false,
    evidence:record
  });
});

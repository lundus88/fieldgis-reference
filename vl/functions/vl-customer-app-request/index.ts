import "jsr:@supabase/functions-js@2.5.0/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2.112.2";

const SUPABASE_URL=Deno.env.get("SUPABASE_URL")!;
const ANON_KEY=Deno.env.get("SUPABASE_ANON_KEY")!;
const SERVICE_ROLE=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const service=createClient(SUPABASE_URL,SERVICE_ROLE,{auth:{persistSession:false}});
const CORS={"access-control-allow-origin":"*","access-control-allow-headers":"authorization,apikey,content-type","access-control-allow-methods":"POST,OPTIONS"};
const J=(body:unknown,status=200)=>new Response(JSON.stringify(body),{status,headers:{...CORS,"content-type":"application/json","cache-control":"no-store"}});
const ALLOWED_PRODUCTS=new Set(["auto","web","pwa","mobile","gis","api"]);

Deno.serve(async(req)=>{
  if(req.method==="OPTIONS") return new Response(null,{status:204,headers:CORS});
  if(req.method!=="POST") return J({error:"POST required",blocked:true},405);

  const auth=req.headers.get("authorization")||"";
  if(!auth.startsWith("Bearer ")) return J({error:"authenticated bearer token required",blocked:true},401);

  try{
    const token=auth.slice(7);
    const userClient=createClient(SUPABASE_URL,ANON_KEY,{auth:{persistSession:false},global:{headers:{Authorization:`Bearer ${token}`}}});
    const {data:{user},error:userError}=await userClient.auth.getUser(token);
    if(userError||!user) return J({error:"invalid or expired session",blocked:true},401);

    const body=await req.json().catch(()=>({}));
    const projectId=String(body.project_id||"");
    const title=String(body.title||"").trim();
    const prompt=String(body.prompt||"").trim();
    const product=String(body.preferred_product||"auto").toLowerCase();
    const launch=body.launch!==false;

    if(!projectId) return J({error:"project_id required",blocked:true},400);
    if(title.length<2||title.length>120) return J({error:"title must be 2-120 characters",blocked:true},400);
    if(prompt.length<20||prompt.length>10000) return J({error:"prompt must be 20-10000 characters",blocked:true},400);
    if(!ALLOWED_PRODUCTS.has(product)) return J({error:"preferred_product not allowed",blocked:true},400);

    const {data:membership,error:membershipError}=await service.from("project_members").select("role").eq("project_id",projectId).eq("user_id",user.id).maybeSingle();
    if(membershipError) return J({error:"membership lookup failed",blocked:true},500);
    if(!membership||!["owner","admin","builder"].includes(String(membership.role))) return J({error:"project access denied",blocked:true},403);
    if(launch&&!["owner","admin"].includes(String(membership.role))) return J({error:"owner/admin required to launch",blocked:true},403);

    const compilerPrompt=product==="auto"?prompt:`Build a ${product} application. ${prompt}`;
    const {data,error}=await service.rpc("vl_submit_customer_app_request",{p_project_id:projectId,p_user_id:user.id,p_prompt:compilerPrompt,p_title:title,p_launch:launch});
    if(error) return J({error:error.message,blocked:true,production_locked:true},409);

    return J({ok:true,result:data,production_locked:true,human_production_approval_required:true});
  }catch(e){return J({error:String((e as Error).message||e),blocked:true,production_locked:true},400)}
});

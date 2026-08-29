import "jsr:@supabase/functions-js@2/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";
import { createRemoteJWKSet, jwtVerify } from "npm:jose@6.2.10";

const SUPABASE_URL=Deno.env.get("SUPABASE_URL")!;
const SERVICE_ROLE=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const ISSUER="https://token.actions.githubusercontent.com";
const AUDIENCE="vrs-certification-depth";
const REPOSITORY="lundus88/fieldgis-reference";
const WORKFLOW_REF="lundus88/fieldgis-reference/.github/workflows/vl-certification-depth.yml@refs/heads/main";
const MAIN_REF="refs/heads/main";
const ALLOWED=new Set(["web-react-v1","pwa-react-v1","mobile-flutter-v1","gis-web-v1","api-service-v1"]);
const JWKS=createRemoteJWKSet(new URL(`${ISSUER}/.well-known/jwks`));
const sb=createClient(SUPABASE_URL,SERVICE_ROLE,{auth:{persistSession:false}});
const J=(body:unknown,status=200)=>new Response(JSON.stringify(body),{status,headers:{"content-type":"application/json"}});

async function verifyOidc(token:string){
  const {payload}=await jwtVerify(token,JWKS,{issuer:ISSUER,audience:AUDIENCE,algorithms:["RS256"],clockTolerance:60});
  const workflowRef=String(payload.job_workflow_ref||payload.workflow_ref||"");
  if(payload.repository!==REPOSITORY||payload.ref!==MAIN_REF||workflowRef!==WORKFLOW_REF) throw new Error("OIDC identity not allowed");
  return {run_id:String(payload.run_id||""),sha:String(payload.sha||""),workflow_ref:workflowRef,actor:String(payload.actor||"")};
}

Deno.serve(async(req)=>{
  if(req.method!=="POST") return J({error:"POST required"},405);
  const auth=req.headers.get("authorization")||"";
  if(!auth.startsWith("Bearer ")) return J({error:"GitHub OIDC bearer token required"},401);
  try{
    const identity=await verifyOidc(auth.slice(7));
    const body=await req.json().catch(()=>({}));
    const builder=String(body.builder_key||"");
    const runCount=Number(body.run_count??2);
    if(!ALLOWED.has(builder)) return J({error:"builder not allowed",blocked:true},400);
    if(!Number.isInteger(runCount)||runCount<1||runCount>2) return J({error:"run_count must be 1 or 2",blocked:true},400);
    const {data,error}=await sb.rpc("enqueue_vrs_golden_certification_runs",{p_builder_key:builder,p_run_count:runCount});
    if(error) return J({error:error.message,blocked:true,builder_key:builder},409);
    return J({ok:true,builder_key:builder,authority:"golden-certification-only",identity,result:data,production_locked:true});
  }catch(e){return J({error:String((e as Error).message||e),blocked:true},401)}
});

import { createClient } from '/tmp/vl-realtime-proof/node_modules/@supabase/supabase-js/dist/main/index.js';

const url=process.env.VL_RT_URL;
const key=process.env.VL_RT_KEY;
const nonce=process.env.VL_RT_NONCE;
if(!url||!key||!nonce) throw new Error('missing realtime proof configuration');

const sb=createClient(url,key,{auth:{persistSession:false,autoRefreshToken:false}});
let done=false;
let timer;
const finish=async(code,message)=>{
  if(done)return;
  done=true;
  clearTimeout(timer);
  console.log(message);
  try{await sb.removeAllChannels();}catch{}
  setTimeout(()=>process.exit(code),100);
};

const channel=sb
  .channel('vl-operational-proof-'+nonce)
  .on('postgres_changes',{
    event:'INSERT',
    schema:'public',
    table:'realtime_e2e_probe',
    filter:`nonce=eq.${nonce}`
  },payload=>{
    const got=payload?.new?.nonce;
    if(got===nonce){
      finish(0,`REALTIME_E2E_PASS nonce=${nonce} id=${payload.new.id}`);
    }
  })
  .subscribe(status=>{
    console.log('REALTIME_STATUS='+status);
    if(status==='SUBSCRIBED') console.log('REALTIME_SUBSCRIBED nonce='+nonce);
    if(status==='CHANNEL_ERROR'||status==='TIMED_OUT'||status==='CLOSED'){
      finish(2,'REALTIME_E2E_FAIL status='+status);
    }
  });

timer=setTimeout(()=>finish(3,'REALTIME_E2E_FAIL timeout waiting for matching INSERT'),120000);

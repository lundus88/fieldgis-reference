// Repository-only PostgreSQL fixture. Never connects to Supabase or produces
// release/certification records. This is not full VL schema or PostgREST validation.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { PGlite } from '@electric-sql/pglite';
import { pgcrypto } from '@electric-sql/pglite/contrib/pgcrypto';

const root = fileURLToPath(new URL('../../', import.meta.url));
const read = path => readFileSync(`${root}${path}`, 'utf8');
const migration = read('migrations/20260914_security_invoker_rpc_guarded_entry.sql');
const founder = read('migrations/20260901_founder_internal_usage_guardrails.sql');
const execution = read('migrations/20260901_assisted_build_execution_gate.sql');
const alignment = read('migrations/20260901_assisted_build_product_alignment.sql');
const liveAlignment = read('migrations/20260831_product_alignment_live_gate.sql');
const mergedBoundary = read('migrations/20260914_public_security_definer_boundary.sql');
const functionSql = (source, signature) => {
  const start = source.indexOf(`create or replace function ${signature}`);
  assert.ok(start >= 0, `missing historical function ${signature}`);
  return source.slice(start, source.indexOf('$$;', start) + 3);
};
const project = '10000000-0000-4000-8000-000000000001';
const otherProject = '10000000-0000-4000-8000-000000000002';
const owner = '20000000-0000-4000-8000-000000000001';
const admin = '20000000-0000-4000-8000-000000000002';
const member = '20000000-0000-4000-8000-000000000003';
const outsider = '20000000-0000-4000-8000-000000000004';
const answers = {
  problem: 'Track incoming survey jobs and their progress',
  users: 'Survey operations coordinator',
  current: 'Record jobs in a spreadsheet', payments: 'no', compliance: 'Access by authorised staff only',
};
const structured = { required_features: ['Register survey job', 'View job progress'], proposed_workflow: 'Register and track survey jobs.' };
const publicSignatures = [
  'public.request_vrs_internal_usage_override(uuid,text,integer)',
  'public.vl_get_assisted_build_quote(text)',
  'public.vl_prepare_assisted_build_product_alignment(jsonb,jsonb)',
];
// Exact count predicates read from the existing production evaluator, 2026-09-14.
// Only SELECTs: the evaluator itself is never called and is never altered.
const scanner = `select
  (select count(*)::int from pg_class c join pg_namespace n on n.oid=c.relnamespace
   where n.nspname='public' and c.relkind='r' and c.relrowsecurity=false) as public_tables_without_rls,
  (select count(*)::int from pg_proc p join pg_namespace n on n.oid=p.pronamespace
   where n.nspname='public' and p.prokind='f' and p.prosecdef
   and (has_function_privilege('public',p.oid,'EXECUTE') or has_function_privilege('anon',p.oid,'EXECUTE')
        or has_function_privilege('authenticated',p.oid,'EXECUTE'))) as public_security_definer_exposed_to_client_roles`;

test('VL RPC boundary on isolated PostgreSQL fixture', async t => {
  const db = new PGlite({ extensions: { pgcrypto } });
  const row = async (sql, params = []) => (await db.query(sql, params)).rows[0];
  const asRole = async (role, claims, fn) => {
    assert.ok(['anon', 'authenticated', 'service_role'].includes(role));
    await db.exec(`set role ${role}`);
    try {
      await db.query("select set_config('request.jwt.claims',$1,false)", [JSON.stringify(claims)]);
      return await fn();
    } finally {
      await db.exec('reset role');
      await db.query("select set_config('request.jwt.claims','{}',false)");
    }
  };
  const auth = (fn, uid = owner, aal = 'aal2') => asRole('authenticated', { sub: uid, aal }, fn);
  const override = (duration = 60, reason = 'Explicit fixture-only usage reason', pid = project) =>
    row('select public.request_vrs_internal_usage_override($1,$2,$3) as result', [pid, reason, duration]);
  const quote = complexity => row('select public.vl_get_assisted_build_quote($1) as result', [complexity]);
  const prepare = (a = answers, s = structured) => row(
    'select public.vl_prepare_assisted_build_product_alignment($1,$2) as result', [a, s]);
  const counts = () => row(`select
    (select count(*)::int from private.internal_usage_overrides) as overrides,
    (select count(*)::int from private.internal_usage_audit) as audit`);
  const denied = (fn, code = '42501', message = undefined) => assert.rejects(fn, e => {
    assert.equal(e.code, code);
    if (message) assert.match(e.message, message);
    return true;
  });
  try {
    await db.exec(`
      create role anon nologin;
      create role authenticated nologin;
      create role service_role nologin bypassrls;
      create schema auth;
      create schema private;
      create schema extensions;
      create extension pgcrypto with schema extensions;
      grant usage on schema public, auth, private to anon, authenticated, service_role;
      create function auth.jwt() returns jsonb language sql stable as
        $$select coalesce(nullif(current_setting('request.jwt.claims',true),'')::jsonb,'{}'::jsonb)$$;
      create function auth.uid() returns uuid language sql stable as
        $$select (auth.jwt()->>'sub')::uuid$$;
      create table public.projects(id uuid primary key);
      create table public.project_members(project_id uuid, user_id uuid, role text);
      create table public.plan_catalog(plan_key text primary key, is_public boolean, limits jsonb);
      alter table public.projects enable row level security;
      alter table public.project_members enable row level security;
      alter table public.plan_catalog enable row level security;
      insert into public.projects values('${project}'),('${otherProject}');
      insert into public.project_members values
        ('${project}','${owner}','owner'),('${project}','${admin}','admin'),('${project}','${member}','member');
      insert into public.plan_catalog values('launch_pilot',true,'{}');
    `);
    // Load the actual pre-fix functions and table constraints, not a rewritten
    // approximation. Unrelated quota/runner triggers need the absent full schema.
    await db.exec(founder.split('create or replace function private.enforce_public_factory_quota()')[0] + '\ncommit;');
    await db.exec(execution.split('create or replace function private.enforce_assisted_build_execution_gate()')[0]);
    await db.exec(functionSql(liveAlignment, 'private.validate_product_alignment('));
    await db.exec(alignment);

    let oldAlignment;
    const oldQuotes = {};
    await t.test('baseline reproduces the three exposed public definers', async () => {
      assert.deepEqual(await row(scanner), { public_tables_without_rls: 0, public_security_definer_exposed_to_client_roles: 3 });
      for (const band of ['low','medium','high']) oldQuotes[band] = (await auth(() => quote(band))).result;
      oldAlignment = (await auth(() => prepare())).result;
      const version = await row('select version() as version');
      assert.match(version.version, /^PostgreSQL 17\./, 'fixture must match the production PostgreSQL major');
      t.diagnostic(`Fixture engine: ${version.version}`);
    });
    await t.test('merged PR #216 closes public exposure but retains three client-executable private definers', async () => {
      await db.exec(mergedBoundary);
      assert.deepEqual(await row(scanner),{public_tables_without_rls:0,public_security_definer_exposed_to_client_roles:0});
      assert.equal((await row(`select count(*)::int as n from pg_proc p join pg_namespace n on n.oid=p.pronamespace
        where n.nspname='private' and p.prosecdef and has_function_privilege('authenticated',p.oid,'EXECUTE')`)).n,3);
      assert.deepEqual((await auth(()=>prepare())).result,oldAlignment);
      for (const band of ['low','medium','high']) assert.deepEqual((await auth(()=>quote(band))).result,oldQuotes[band]);
    });
    const unchanged = await row(`select jsonb_build_object(
      'projects',(select jsonb_agg(p) from public.projects p),
      'members',(select jsonb_agg(p) from public.project_members p),
      'plans',(select jsonb_agg(p) from public.plan_catalog p),
      'cost_policy',(select jsonb_agg(p) from private.assisted_build_cost_policy p)) as data`);
    await t.test('migration applies and replays without changing existing data', async () => {
      await db.exec(migration);
      await db.exec(migration);
      assert.deepEqual(await counts(), { overrides: 0, audit: 0 });
    });
    await t.test('unchanged scanner predicates retain zero public exposure after the successor migration', async () => {
      assert.deepEqual(await row(scanner), { public_tables_without_rls: 0, public_security_definer_exposed_to_client_roles: 0 });
    });

    for (const signature of publicSignatures) {
      await t.test(`${signature}: INVOKER, authenticated EXECUTE, PUBLIC/anon denied`, async () => {
        assert.deepEqual(await row(`select prosecdef,
          has_function_privilege('public',oid,'EXECUTE') as public_execute,
          has_function_privilege('anon',oid,'EXECUTE') as anon_execute,
          has_function_privilege('authenticated',oid,'EXECUTE') as authenticated_execute
          from pg_proc where oid=$1::regprocedure`, [signature]),
        { prosecdef: false, public_execute: false, anon_execute: false, authenticated_execute: true });
      });
    }
    await t.test('all new privileged helpers deny client execution; paths are locked', async () => {
      const helper = await row(`select prosecdef,proconfig,
        has_function_privilege('public',oid,'EXECUTE') as public_execute,
        has_function_privilege('anon',oid,'EXECUTE') as anon_execute,
        has_function_privilege('authenticated',oid,'EXECUTE') as authenticated_execute
        from pg_proc where oid='private.request_vrs_internal_usage_override_impl()'::regprocedure`);
      assert.deepEqual(helper, { prosecdef:true, proconfig:['search_path=""'], public_execute:false, anon_execute:false, authenticated_execute:false });
      assert.equal((await row(`select count(*)::int as n from pg_proc p join pg_namespace n on n.oid=p.pronamespace
        where n.nspname='private' and p.prosecdef and
        (has_function_privilege('public',p.oid,'EXECUTE') or has_function_privilege('anon',p.oid,'EXECUTE') or has_function_privilege('authenticated',p.oid,'EXECUTE'))`)).n, 0);
      for (const sig of [...publicSignatures, 'private.build_assisted_build_product_alignment(jsonb,jsonb)', 'private.validate_product_alignment(jsonb)']) {
        assert.deepEqual((await row('select proconfig from pg_proc where oid=$1::regprocedure',[sig])).proconfig,['search_path=""']);
      }
    });
    await t.test('alignment helpers are nonprivileged; only authenticated/backend may call', async () => {
      for (const sig of ['private.build_assisted_build_product_alignment(jsonb,jsonb)','private.validate_product_alignment(jsonb)']) {
        const p = await row(`select prosecdef,has_function_privilege('anon',oid,'EXECUTE') as anon_execute,
          has_function_privilege('authenticated',oid,'EXECUTE') as authenticated_execute,
          has_function_privilege('service_role',oid,'EXECUTE') as backend_execute from pg_proc where oid=$1::regprocedure`, [sig]);
        assert.deepEqual(p,{prosecdef:false,anon_execute:false,authenticated_execute:true,backend_execute:true});
      }
    });
    for (const [name, fn] of [['override',()=>override()],['quote',()=>quote('low')],['alignment',()=>prepare()]]) {
      await t.test(`anon cannot invoke ${name}, even with a supplied uid/AAL2 claim`, () =>
        asRole('anon',{sub:owner,aal:'aal2'},()=>denied(fn)));
      await t.test(`authenticated role without user identity cannot invoke ${name}`, () =>
        asRole('authenticated',{},()=>denied(fn,name==='override'?'P0001':'42501',/authenticated user required/)));
    }
    await t.test('direct helper execution and attaching helper as a client trigger fail', async () => {
      for (const role of ['anon','authenticated']) await asRole(role,{sub:owner,aal:'aal2'},()=>
        denied(()=>db.query('select private.request_vrs_internal_usage_override_impl()')));
      await auth(async () => {
        await db.exec('create temporary table client_trigger_target(n integer)');
        await denied(()=>db.exec(`create trigger client_trigger before insert on client_trigger_target
          for each row execute function private.request_vrs_internal_usage_override_impl()`));
        await db.exec('drop table client_trigger_target');
      });
      for (const role of ['anon','authenticated']) await asRole(role,{sub:owner,aal:'aal2'},async () => {
        await denied(()=>row('select private.request_vrs_internal_usage_override_impl($1,$2,60)',[project,'Explicit legacy helper reason']));
        await denied(()=>row("select private.vl_get_assisted_build_quote_impl('low')"));
        await denied(()=>row('select private.vl_prepare_assisted_build_product_alignment_impl($1,$2)',[answers,structured]));
      });
    });
    for (const aal of ['aal1','',null]) {
      await t.test(`override requires AAL2 (reject ${JSON.stringify(aal)})`, () =>
        auth(()=>denied(()=>override(),'P0001',/AAL2 MFA required/),owner,aal));
    }
    for (const [label,uid,pid] of [['ordinary member',member,project],['nonmember',outsider,project],['other project',owner,otherProject]]) {
      await t.test(`override denies ${label}`, () => auth(()=>denied(()=>override(60,undefined,pid),'P0001',/owner\/admin/),uid));
    }
    for (const reason of [null,'','           ','12345678901','   too short  ']) {
      await t.test(`override rejects short/empty reason ${JSON.stringify(reason)}`, () =>
        auth(()=>denied(()=>override(60,reason),'P0001',/reason must be explicit/)));
    }
    for (const duration of [null,0,-1,241]) {
      await t.test(`override rejects invalid duration ${duration}`, () =>
        auth(()=>denied(()=>override(duration),'P0001',/duration outside 1\.\.240/)));
    }
    await t.test('every rejected override leaves zero override/audit rows', async () => {
      assert.deepEqual(await counts(),{overrides:0,audit:0});
    });
    for (const [uid,duration] of [[owner,1],[admin,240]]) {
      await t.test(`authorised ${uid===owner?'owner':'admin'} can create ${duration}-minute audited override`, async () => {
        const result=(await auth(()=>override(duration,'  123456789012  '),uid)).result;
        assert.deepEqual(Object.keys(result).sort(),['ok','override_id','expires_in_minutes','production_approval_bypassed','production_promotion_bypassed'].sort());
        assert.equal(result.ok,true); assert.equal(result.expires_in_minutes,duration);
        assert.equal(result.production_approval_bypassed,false); assert.equal(result.production_promotion_bypassed,false);
        const saved=await row(`select requested_by,reason,revoked_at,
          extract(epoch from expires_at-valid_from)::int as seconds
          from private.internal_usage_overrides where id=$1`,[result.override_id]);
        assert.deepEqual(saved,{requested_by:uid,reason:'123456789012',revoked_at:null,seconds:duration*60});
        const audit=await row(`select actor_user_id,event_type,evidence from private.internal_usage_audit
          where evidence->>'override_id'=$1`,[result.override_id]);
        assert.equal(audit.actor_user_id,uid); assert.equal(audit.event_type,'override_created');
        assert.equal(audit.evidence.aal,'aal2');
        assert.equal(audit.evidence.production_approval_changed,false);
        assert.equal(audit.evidence.production_promotion_changed,false);
      });
    }
    await t.test('omitted duration retains the 60-minute public default', async () => {
      const result=await auth(()=>row('select public.request_vrs_internal_usage_override($1,$2) as result',[project,'Explicit default duration reason']));
      assert.equal(result.result.expires_in_minutes,60);
    });
    await t.test('private INSERT route cannot bypass identity, MFA, membership or fabricate output', async () => {
      const insert=()=>row(`insert into private.internal_usage_override_request(project_id,reason,duration_minutes)
        values($1,$2,60) returning result`,[project,'Explicit direct-route fixture reason']);
      await asRole('anon',{sub:owner,aal:'aal2'},()=>denied(insert));
      await asRole('authenticated',{},()=>denied(insert,'P0001',/authenticated user required/));
      await auth(()=>denied(insert,'P0001',/AAL2/),owner,'aal1');
      await auth(()=>denied(insert,'P0001',/owner\/admin/),member);
      await auth(()=>denied(()=>db.query(`insert into private.internal_usage_override_request(result) values('{}')`)));
      await auth(()=>denied(()=>db.query(`update private.internal_usage_override_request set duration_minutes=240`),'55000',/cannot update view/));
      await auth(()=>denied(()=>db.query(`delete from private.internal_usage_override_request`),'55000',/cannot delete from view/));
      assert.equal((await row("select has_column_privilege('authenticated','private.internal_usage_override_request','duration_minutes','UPDATE') as allowed")).allowed,false);
      assert.equal((await row("select has_table_privilege('authenticated','private.internal_usage_override_request','DELETE') as allowed")).allowed,false);
      assert.deepEqual((await auth(()=>db.query('select result from private.internal_usage_override_request'))).rows,[]);
    });
    await t.test('failed audit write atomically rolls back the override insert', async () => {
      const before=await counts();
      await db.exec(`create function private.fixture_reject_audit() returns trigger language plpgsql as
        $$begin raise exception 'fixture audit failure'; end$$;
        create trigger fixture_reject_audit before insert on private.internal_usage_audit
        for each row execute function private.fixture_reject_audit()`);
      await auth(()=>denied(()=>override(),'P0001',/fixture audit failure/));
      assert.deepEqual(await counts(),before);
      await db.exec('drop trigger fixture_reject_audit on private.internal_usage_audit; drop function private.fixture_reject_audit()');
    });
    for (const band of ['low','medium','high']) {
      await t.test(`${band} quote JSON exactly matches the historical contract`, async () => {
        assert.deepEqual((await auth(()=>quote(band))).result,oldQuotes[band]);
      });
    }
    for (const band of [null,'','unsupported']) {
      await t.test(`quote rejects unavailable policy ${JSON.stringify(band)}`, () =>
        auth(()=>denied(()=>quote(band),'P0001',/policy unavailable/)));
    }
    await t.test('disabled policy is never exposed through the facade or projection', async () => {
      await db.exec("update private.assisted_build_cost_policy set enabled=false where complexity_class='low'");
      await auth(()=>denied(()=>quote('low'),'P0001',/policy unavailable/));
      assert.equal((await auth(()=>row("select count(*)::int as n from private.assisted_build_quote_catalog where complexity_class='low'"))).n,0);
      await db.exec("update private.assisted_build_cost_policy set enabled=true where complexity_class='low'");
    });
    await t.test('raw private tables and projection writes are inaccessible to clients', async () => {
      for (const role of ['anon','authenticated']) await asRole(role,{sub:owner,aal:'aal2'},async () => {
        for (const name of ['internal_usage_overrides','internal_usage_audit','assisted_build_cost_policy']) {
          await denied(()=>db.query(`select * from private.${name}`));
          await denied(()=>db.query(`delete from private.${name}`));
        }
        await denied(()=>db.query("update private.assisted_build_quote_catalog set complexity_class='x'"));
        await denied(()=>db.query("insert into private.assisted_build_quote_catalog(complexity_class) values('x')"));
      });
      await asRole('anon',{},()=>denied(()=>db.query('select * from private.assisted_build_quote_catalog')));
      assert.equal((await asRole('authenticated',{},()=>row('select count(*)::int as n from private.assisted_build_quote_catalog'))).n,0);
    });
    await t.test('alignment JSON and both SHA-256 hashes exactly match historical output', async () => {
      assert.deepEqual((await auth(()=>prepare())).result,oldAlignment);
      assert.equal(oldAlignment.validation.ok,true);
      assert.equal(oldAlignment.generated_for_review,true);
      assert.equal(oldAlignment.production_approval_performed,false);
      assert.equal(oldAlignment.production_promotion_performed,false);
    });
    for (const [a,s] of [[null,structured],[{},structured],[answers,null],[answers,{required_features:[]}],[answers,{required_features:['']}]] ) {
      await t.test(`alignment rejects malformed preparation ${JSON.stringify([a,s])}`, () =>
        auth(()=>denied(()=>prepare(a,s),'P0001')));
    }
    await t.test('quote and alignment succeed in a READ ONLY transaction', async () => {
      const before=await counts();
      await auth(async () => {
        await db.exec('begin read only');
        try { await quote('medium'); await prepare(); } finally { await db.exec('rollback'); }
      });
      assert.deepEqual(await counts(),before);
    });
    await t.test('temporary lookalike objects cannot divert privileged writes or policy reads', async () => {
      await auth(async () => {
        await db.exec(`create temporary table internal_usage_overrides(id uuid);
          create temporary table assisted_build_cost_policy(complexity_class text);
          set search_path=pg_temp,public`);
        try { assert.deepEqual((await quote('low')).result,oldQuotes.low); await override(); }
        finally { await db.exec('drop table pg_temp.internal_usage_overrides; drop table pg_temp.assisted_build_cost_policy; reset search_path'); }
      });
    });
    await t.test('replay repairs unintended view grants and keeps existing audited records', async () => {
      const before=await counts();
      await db.exec(`grant update (duration_minutes), insert (result) on private.internal_usage_override_request to authenticated;
        grant select (quote) on private.assisted_build_quote_catalog to anon`);
      await db.exec(migration);
      assert.deepEqual(await counts(),before);
      assert.equal((await row("select has_column_privilege('authenticated','private.internal_usage_override_request','result','INSERT') as allowed")).allowed,false);
      assert.equal((await row("select has_column_privilege('authenticated','private.internal_usage_override_request','duration_minutes','UPDATE') as allowed")).allowed,false);
      assert.equal((await row("select has_column_privilege('anon','private.assisted_build_quote_catalog','quote','SELECT') as allowed")).allowed,false);
    });
    await t.test('unrelated fixture data and final scanner evidence remain unchanged', async () => {
      assert.deepEqual(await row(`select jsonb_build_object(
        'projects',(select jsonb_agg(p) from public.projects p),
        'members',(select jsonb_agg(p) from public.project_members p),
        'plans',(select jsonb_agg(p) from public.plan_catalog p),
        'cost_policy',(select jsonb_agg(p order by complexity_class) from private.assisted_build_cost_policy p)) as data`),
      { data:{...unchanged.data,cost_policy:[...unchanged.data.cost_policy].sort((a,b)=>a.complexity_class.localeCompare(b.complexity_class))} });
      assert.deepEqual(await row(scanner),{public_tables_without_rls:0,public_security_definer_exposed_to_client_roles:0});
      await db.exec(read('tests/database-security/privilege-evidence.sql'));
    });
  } finally { await db.close(); }
});

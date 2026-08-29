do $do$
declare
  v_builder text;
  v_result jsonb;
begin
  foreach v_builder in array array['web-react-v1','pwa-react-v1'] loop
    select public.evaluate_builder_certification(v_builder,false) into v_result;
    if coalesce((v_result->>'distinct_run_count')::int,0) < 3
       or v_result->>'decision' <> 'certified'
       or coalesce((v_result->>'score')::numeric,0) < 1 then
      raise exception 'builder % is not eligible for minimum_distinct_runs=3: %',v_builder,v_result;
    end if;
  end loop;

  update public.builder_certification_policies
  set minimum_distinct_runs=3,updated_at=now()
  where builder_key in ('web-react-v1','pwa-react-v1') and status='active';

  foreach v_builder in array array['web-react-v1','pwa-react-v1'] loop
    select public.evaluate_builder_certification(v_builder,false) into v_result;
    if v_result->>'decision' <> 'certified'
       or coalesce((v_result->>'distinct_run_count')::int,0) < 3 then
      raise exception 'builder % failed post-update certification: %',v_builder,v_result;
    end if;
  end loop;
end
$do$;

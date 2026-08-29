-- Fail-closed certification-depth hardening.
-- This migration refuses to raise the threshold unless every active production builder
-- already has at least 3 factory runs containing the complete required evidence set.
DO $$
DECLARE
  b text;
  req text[];
  req_count integer;
  run_count integer;
BEGIN
  FOREACH b IN ARRAY ARRAY['web-react-v1','pwa-react-v1','mobile-flutter-v1','gis-web-v1','api-service-v1']
  LOOP
    SELECT coalesce(array_agg(value order by value),'{}'::text[])
      INTO req
    FROM public.builder_certification_policies p,
         LATERAL jsonb_array_elements_text(p.required_evidence)
    WHERE p.builder_key=b AND p.status='active';

    req_count := cardinality(req);
    IF req_count = 0 THEN
      RAISE EXCEPTION 'No active certification evidence policy for %', b;
    END IF;

    SELECT count(*)::int INTO run_count
    FROM (
      SELECT factory_run_id
      FROM public.builder_certification_evidence
      WHERE builder_key=b
        AND evidence_status='pass'
        AND factory_run_id IS NOT NULL
        AND evidence_type = ANY(req)
      GROUP BY factory_run_id
      HAVING count(DISTINCT evidence_type)=req_count
    ) complete_runs;

    IF run_count < 3 THEN
      RAISE EXCEPTION 'Certification depth hardening blocked for %: only % complete runs (need 3)', b, run_count;
    END IF;
  END LOOP;

  UPDATE public.builder_certification_policies
  SET minimum_distinct_runs=3, updated_at=now()
  WHERE builder_key IN ('web-react-v1','pwa-react-v1','mobile-flutter-v1','gis-web-v1','api-service-v1')
    AND status='active';
END $$;

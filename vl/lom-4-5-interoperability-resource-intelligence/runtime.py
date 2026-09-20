from dataclasses import dataclass
from typing import Iterable, List, Dict, Any

HUMAN_ONLY = {
    'PROTECTED_MAIN_MERGE','PRODUCTION_RELEASE','PRODUCTION_DATA_MUTATION',
    'AUTHORITY_WIDENING','AUTH_SECURITY_POLICY_CHANGE','DATA_DELETION',
    'CUSTOMER_COMMITMENT','BID_SUBMISSION','PRICING_COMMITMENT',
    'CONTRACT_COMMITMENT','FINANCIAL_COMMITMENT'
}

@dataclass(frozen=True)
class Adapter:
    adapter_id: str
    provider: str
    status: str
    capabilities: tuple
    retention: str
    training: str
    quality: float
    latency_ms: int
    cost_per_1k: float

@dataclass(frozen=True)
class WorkItem:
    work_id: str
    capability: str
    input_tokens: int
    output_tokens: int
    max_cost: float
    max_latency_ms: int
    min_quality: float
    priority: int
    tenant: str
    data_class: str = 'internal'

class InteropResourceRuntime:
    def _privacy_ok(self, adapter: Adapter, item: WorkItem) -> bool:
        sensitive = item.data_class in {'secret','credential','customer_private','proprietary_dataset','production_data'}
        if sensitive:
            return adapter.retention == 'none' and adapter.training == 'disabled'
        return adapter.training == 'disabled'

    def route(self, adapters: Iterable[Adapter], item: WorkItem) -> Dict[str, Any]:
        if item.capability in HUMAN_ONLY:
            return {'decision':'HUMAN_REVIEW','reason':'HUMAN_ONLY_TARGET'}
        if min(item.input_tokens, item.output_tokens, item.max_cost, item.max_latency_ms, item.min_quality) < 0:
            return {'decision':'HOLD','reason':'INVALID_REQUIREMENT'}

        candidates = []
        rejected = []
        for a in adapters:
            reasons = []
            if a.status != 'active': reasons.append('inactive')
            if item.capability not in a.capabilities: reasons.append('capability')
            if not self._privacy_ok(a, item): reasons.append('privacy')
            estimated_cost = ((item.input_tokens + item.output_tokens) / 1000.0) * a.cost_per_1k
            if estimated_cost > item.max_cost: reasons.append('cost')
            if a.latency_ms > item.max_latency_ms: reasons.append('latency')
            if a.quality < item.min_quality: reasons.append('quality')
            if reasons:
                rejected.append({'adapter_id':a.adapter_id,'reasons':reasons})
                continue
            score = (a.quality * 100.0) - (a.latency_ms / 1000.0) - estimated_cost
            candidates.append((score, a.adapter_id, estimated_cost))

        if not candidates:
            return {'decision':'HOLD','reason':'NO_COMPATIBLE_ADAPTER','rejected':rejected}
        candidates.sort(key=lambda x: (-x[0], x[1]))
        selected = candidates[0]
        return {
            'decision':'ROUTE',
            'adapter_id':selected[1],
            'estimated_cost':round(selected[2],8),
            'fallback_chain':[x[1] for x in candidates[1:]],
            'rejected':rejected,
            'production_locked':True,
        }

    def enforce_budget(self, budget: Dict[str,int], requested: Dict[str,int]) -> Dict[str,str]:
        keys = ('tokens','cost_microunits','steps','time_seconds','retries')
        for key in keys:
            if key not in budget or key not in requested or budget[key] < 0 or requested[key] < 0:
                return {'decision':'HOLD','reason':'INVALID_BUDGET'}
            if requested[key] > budget[key]:
                return {'decision':'HOLD','reason':'BUDGET_EXPANSION_BLOCKED'}
        return {'decision':'ALLOW','reason':'WITHIN_GLOBAL_BUDGET'}

    def schedule(self, items: Iterable[WorkItem], max_items: int) -> List[WorkItem]:
        if max_items < 1:
            return []
        ordered = sorted(items, key=lambda w: (-w.priority, w.tenant, w.work_id))
        result, seen = [], set()
        for item in ordered:
            if item.tenant not in seen:
                result.append(item)
                seen.add(item.tenant)
                if len(result) >= max_items:
                    return result
        for item in ordered:
            if item not in result:
                result.append(item)
                if len(result) >= max_items:
                    break
        return result

    def capacity_plan(self, pools: Iterable[Dict[str,Any]], required_cpu: int, required_memory_mb: int) -> Dict[str,Any]:
        if required_cpu < 1 or required_memory_mb < 1:
            return {'decision':'HOLD','reason':'INVALID_CAPACITY_REQUIREMENT'}
        eligible = []
        for p in pools:
            if p.get('status') != 'certified':
                continue
            if p.get('environment') not in {'development','staging'}:
                continue
            if p.get('ambient_production_credentials') is not False:
                continue
            if p.get('cpu_available',0) >= required_cpu and p.get('memory_mb_available',0) >= required_memory_mb:
                eligible.append(p)
        if not eligible:
            return {'decision':'HOLD','reason':'NO_SAFE_CAPACITY'}
        eligible.sort(key=lambda p: (p.get('estimated_hourly_cost',0), -p.get('cpu_available',0), p.get('pool_id','')))
        return {'decision':'RECOMMEND','pool_id':eligible[0]['pool_id'],'autonomous_ceiling':'PREPARE_PR','production_locked':True}

    def autonomous_ceiling(self) -> str:
        return 'PREPARE_PR'

    def allocate_production_capacity(self):
        raise PermissionError('HUMAN_APPROVAL_REQUIRED')


    def resource_mode(self, used_tokens:int, total_tokens:int) -> Dict[str,str]:
        if total_tokens <= 0 or used_tokens < 0 or used_tokens > total_tokens:
            return {'decision':'HOLD','reason':'INVALID_RESOURCE_COUNTER'}
        pct = used_tokens / total_tokens
        if pct >= 0.95:
            return {'decision':'CRITICAL_ONLY','state':'RESOURCE_CONSTRAINED','reserve':'5%'}
        if pct >= 0.85:
            return {'decision':'CONTROLLED_MODE','state':'RESOURCE_CONSTRAINED','reserve':'15%'}
        if pct >= 0.70:
            return {'decision':'SHED_NON_CRITICAL','state':'RESOURCE_PRESSURE','reserve':'30%'}
        return {'decision':'NORMAL','state':'RESOURCE_HEALTHY','reserve':'30%+'}

    def admission_control(self, priority_class:str, mode:str) -> Dict[str,str]:
        allowed={'P0','P1','P2','P3','INTERNAL_EXPERIMENT'}
        if priority_class not in allowed:
            return {'decision':'HOLD','reason':'UNKNOWN_PRIORITY'}
        if mode == 'CRITICAL_ONLY':
            return {'decision':'ALLOW' if priority_class in {'P0','P1'} else 'QUEUE','reason':'CRITICAL_RESERVE'}
        if mode == 'CONTROLLED_MODE':
            return {'decision':'ALLOW' if priority_class in {'P0','P1','P2'} else 'QUEUE','reason':'CONTROLLED_RESERVE'}
        if mode == 'SHED_NON_CRITICAL':
            return {'decision':'QUEUE' if priority_class == 'INTERNAL_EXPERIMENT' else 'ALLOW','reason':'PRESERVE_CUSTOMER_CAPACITY'}
        if mode == 'NORMAL':
            return {'decision':'ALLOW','reason':'RESOURCE_HEALTHY'}
        return {'decision':'HOLD','reason':'UNKNOWN_RESOURCE_MODE'}

    def checkpoint(self, work_id:str, step:int, artifact_refs:List[str], decision_refs:List[str], next_action:str) -> Dict[str,Any]:
        if not work_id or step < 0 or not next_action:
            return {'decision':'HOLD','reason':'INVALID_CHECKPOINT'}
        if not artifact_refs and not decision_refs:
            return {'decision':'HOLD','reason':'EMPTY_CHECKPOINT_EVIDENCE'}
        return {
            'decision':'CHECKPOINTED',
            'state':'CHECKPOINTED',
            'work_id':work_id,
            'step':step,
            'artifact_refs':list(artifact_refs),
            'decision_refs':list(decision_refs),
            'next_action':next_action,
            'resume_from_zero':False
        }

    def resume_plan(self, checkpoint:Dict[str,Any], fallback_chain:List[str]) -> Dict[str,Any]:
        if checkpoint.get('decision') != 'CHECKPOINTED':
            return {'decision':'HOLD','reason':'VALID_CHECKPOINT_REQUIRED'}
        if not checkpoint.get('work_id') or checkpoint.get('step',-1) < 0:
            return {'decision':'HOLD','reason':'INVALID_CHECKPOINT'}
        return {
            'decision':'RESUME',
            'state':'RESUMED',
            'work_id':checkpoint['work_id'],
            'resume_step':checkpoint['step'],
            'next_action':checkpoint['next_action'],
            'fallback_chain':list(fallback_chain),
            'restart_from_zero':False
        }

    def handle_resource_exhaustion(self, checkpoint_available:bool, fallback_chain:List[str]) -> Dict[str,Any]:
        if checkpoint_available:
            if fallback_chain:
                return {'decision':'FALLBACK_ROUTE','state':'RESOURCE_CONSTRAINED','next_adapter':fallback_chain[0]}
            return {'decision':'WAIT_CAPACITY','state':'WAITING_CAPACITY'}
        return {'decision':'HOLD','state':'RESOURCE_CONSTRAINED','reason':'NO_CHECKPOINT_NO_SAFE_RESTART'}

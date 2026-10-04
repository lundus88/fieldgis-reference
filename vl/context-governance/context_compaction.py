from __future__ import annotations

from hashlib import sha256
import json
import re
from typing import Any, Iterable

SCHEMA = "vl.context-compaction/1"
AUTONOMOUS_CEILING = "PREPARE_PR"
PRODUCTION_AUTHORITY = "HUMAN_ONLY"
PROTECTED_MAIN_MERGE = "HUMAN_ONLY"
EXECUTION_AUTHORITY = "NONE"

TOKEN_RE = re.compile(r"[A-Za-z0-9_./:-]{3,}")


def _sha256_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + sha256(raw).hexdigest()


def _task_terms(task: dict[str, Any]) -> set[str]:
    raw = json.dumps(task, sort_keys=True, ensure_ascii=False)
    return {match.group(0).lower() for match in TOKEN_RE.finditer(raw)}


def _chunk_content(content: str, *, chunk_chars: int) -> list[dict[str, Any]]:
    if chunk_chars <= 0:
        raise ValueError("POSITIVE_CHUNK_BUDGET_REQUIRED")

    lines = content.splitlines(keepends=True)
    if not lines:
        lines = [content]

    chunks: list[dict[str, Any]] = []
    buffer: list[str] = []
    start_line = 1
    current_line = 1
    current_len = 0

    def flush(end_line: int) -> None:
        nonlocal buffer, start_line, current_len
        if not buffer:
            return
        text = "".join(buffer)
        chunks.append({
            "content": text,
            "start_line": start_line,
            "end_line": end_line,
            "char_count": len(text),
        })
        buffer = []
        current_len = 0

    for line in lines:
        remaining = line
        while len(remaining) > chunk_chars:
            if buffer:
                flush(current_line - 1 if current_line > start_line else current_line)
                start_line = current_line
            part = remaining[:chunk_chars]
            chunks.append({
                "content": part,
                "start_line": current_line,
                "end_line": current_line,
                "char_count": len(part),
            })
            remaining = remaining[chunk_chars:]

        if buffer and current_len + len(remaining) > chunk_chars:
            flush(current_line - 1)
            start_line = current_line

        if not buffer:
            start_line = current_line
        buffer.append(remaining)
        current_len += len(remaining)
        current_line += 1

    flush(max(start_line, current_line - 1))
    return chunks


def _chunk_score(content: str, terms: set[str]) -> tuple[int, int]:
    lower = content.lower()
    hits = sum(1 for term in terms if term in lower)
    # Prefer more task-term coverage, then denser/shorter excerpts.
    return hits, -len(content)


def compact_allowed_context(
    allowed_context: Iterable[dict[str, Any]],
    *,
    task: dict[str, Any],
    max_context_chars: int,
    chunk_chars: int = 1200,
) -> dict[str, Any]:
    if not isinstance(max_context_chars, int) or max_context_chars <= 0:
        return {"status": "HOLD", "reason": "POSITIVE_CONTEXT_BUDGET_REQUIRED"}
    if not isinstance(chunk_chars, int) or chunk_chars <= 0:
        return {"status": "HOLD", "reason": "POSITIVE_CHUNK_BUDGET_REQUIRED"}

    resources = [dict(item) for item in allowed_context]
    if not resources:
        return {"status": "HOLD", "reason": "ALLOWED_CONTEXT_REQUIRED"}

    normalized: list[dict[str, Any]] = []
    seen_resources: set[tuple[str, str, str]] = set()
    for item in resources:
        resource_type = str(item.get("resource_type") or "").strip()
        resource = str(item.get("resource") or "").strip()
        data_class = str(item.get("data_class") or "").strip()
        content = item.get("content")
        if not resource_type or not resource or not data_class or not isinstance(content, str) or not content:
            return {"status": "HOLD", "reason": "ALLOWED_CONTEXT_ITEM_INVALID"}
        identity = (resource_type, resource, data_class)
        if identity in seen_resources:
            return {"status": "HOLD", "reason": "DUPLICATE_ALLOWED_RESOURCE"}
        seen_resources.add(identity)
        normalized.append({
            "resource_type": resource_type,
            "resource": resource,
            "data_class": data_class,
            "content": content,
            "content_sha256": _sha256_text(content),
        })

    normalized.sort(key=lambda x: (x["resource_type"], x["resource"], x["data_class"]))
    total_chars = sum(len(item["content"]) for item in normalized)
    terms = _task_terms(task)

    if total_chars <= max_context_chars:
        manifest_body = {
            "schema": SCHEMA,
            "status": "READY",
            "reason": "COMPACTION_NOT_REQUIRED",
            "compacted": False,
            "original_resource_count": len(normalized),
            "selected_resource_count": len(normalized),
            "original_char_count": total_chars,
            "selected_char_count": total_chars,
            "max_context_chars": max_context_chars,
            "source_truth_preserved": True,
            "abstractive_summary_generated": False,
            "dropped_resource_count": 0,
            "selected_excerpts": [
                {
                    "resource_type": item["resource_type"],
                    "resource": item["resource"],
                    "data_class": item["data_class"],
                    "source_content_sha256": item["content_sha256"],
                    "excerpt_sha256": item["content_sha256"],
                    "start_line": 1,
                    "end_line": max(1, len(item["content"].splitlines())),
                    "char_count": len(item["content"]),
                }
                for item in normalized
            ],
            "autonomous_ceiling": AUTONOMOUS_CEILING,
            "production_authority": PRODUCTION_AUTHORITY,
            "protected_main_merge": PROTECTED_MAIN_MERGE,
            "execution_authority": EXECUTION_AUTHORITY,
        }
        context = [
            {
                "resource_type": item["resource_type"],
                "resource": item["resource"],
                "data_class": item["data_class"],
                "content": item["content"],
            }
            for item in normalized
        ]
        return {
            "status": "READY",
            "context": context,
            "manifest": {**manifest_body, "compaction_digest": _digest(manifest_body)},
        }

    effective_chunk_chars = min(chunk_chars, max_context_chars)
    all_chunks: list[dict[str, Any]] = []
    for item in normalized:
        chunks = _chunk_content(item["content"], chunk_chars=effective_chunk_chars)
        if not chunks:
            return {"status": "HOLD", "reason": "RESOURCE_CHUNKING_FAILED"}
        for index, chunk in enumerate(chunks):
            score = _chunk_score(chunk["content"], terms)
            all_chunks.append({
                "resource_type": item["resource_type"],
                "resource": item["resource"],
                "data_class": item["data_class"],
                "source_content_sha256": item["content_sha256"],
                "chunk_index": index,
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
                "content": chunk["content"],
                "char_count": chunk["char_count"],
                "score_hits": score[0],
                "score_density": score[1],
            })

    by_resource: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for chunk in all_chunks:
        key = (chunk["resource_type"], chunk["resource"], chunk["data_class"])
        by_resource.setdefault(key, []).append(chunk)

    selected: list[dict[str, Any]] = []
    selected_ids: set[tuple[str, str, str, int]] = set()
    used_chars = 0

    # Coverage gate: retain at least one excerpt from every governed/allowed resource.
    for key in sorted(by_resource):
        ranked = sorted(
            by_resource[key],
            key=lambda x: (-x["score_hits"], -x["score_density"], x["chunk_index"]),
        )
        best = ranked[0]
        if used_chars + best["char_count"] > max_context_chars:
            return {
                "status": "HOLD",
                "reason": "CONTEXT_BUDGET_INSUFFICIENT_FOR_RESOURCE_COVERAGE",
            }
        selected.append(best)
        selected_ids.add((*key, best["chunk_index"]))
        used_chars += best["char_count"]

    # Fill remaining budget with the most task-relevant excerpts.
    remaining = [
        chunk for chunk in all_chunks
        if (
            chunk["resource_type"],
            chunk["resource"],
            chunk["data_class"],
            chunk["chunk_index"],
        ) not in selected_ids
    ]
    remaining.sort(
        key=lambda x: (
            -x["score_hits"],
            -x["score_density"],
            x["resource_type"],
            x["resource"],
            x["data_class"],
            x["chunk_index"],
        )
    )
    for chunk in remaining:
        if used_chars + chunk["char_count"] <= max_context_chars:
            selected.append(chunk)
            used_chars += chunk["char_count"]

    selected.sort(
        key=lambda x: (
            x["resource_type"],
            x["resource"],
            x["data_class"],
            x["chunk_index"],
        )
    )

    context = [
        {
            "resource_type": item["resource_type"],
            "resource": item["resource"],
            "data_class": item["data_class"],
            "content": item["content"],
            "source_span": {
                "start_line": item["start_line"],
                "end_line": item["end_line"],
            },
            "source_content_sha256": item["source_content_sha256"],
            "excerpt_sha256": _sha256_text(item["content"]),
        }
        for item in selected
    ]

    manifest_body = {
        "schema": SCHEMA,
        "status": "READY",
        "reason": "EXTRACTIVE_CONTEXT_COMPACTION_READY",
        "compacted": True,
        "original_resource_count": len(normalized),
        "selected_resource_count": len({
            (x["resource_type"], x["resource"], x["data_class"]) for x in selected
        }),
        "original_char_count": total_chars,
        "selected_char_count": used_chars,
        "max_context_chars": max_context_chars,
        "source_truth_preserved": True,
        "abstractive_summary_generated": False,
        "dropped_resource_count": 0,
        "selection_basis": "TASK_TERM_EXTRACTIVE_WITH_FULL_RESOURCE_COVERAGE",
        "selected_excerpts": [
            {
                "resource_type": item["resource_type"],
                "resource": item["resource"],
                "data_class": item["data_class"],
                "source_content_sha256": item["source_content_sha256"],
                "excerpt_sha256": _sha256_text(item["content"]),
                "start_line": item["start_line"],
                "end_line": item["end_line"],
                "char_count": item["char_count"],
                "task_term_hits": item["score_hits"],
            }
            for item in selected
        ],
        "autonomous_ceiling": AUTONOMOUS_CEILING,
        "production_authority": PRODUCTION_AUTHORITY,
        "protected_main_merge": PROTECTED_MAIN_MERGE,
        "execution_authority": EXECUTION_AUTHORITY,
    }

    return {
        "status": "READY",
        "context": context,
        "manifest": {**manifest_body, "compaction_digest": _digest(manifest_body)},
    }


def validate_compaction_manifest(manifest: dict[str, Any]) -> dict[str, str]:
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        return {"status": "HOLD", "reason": "CONTEXT_COMPACTION_SCHEMA_INVALID"}
    for key, expected in (
        ("autonomous_ceiling", AUTONOMOUS_CEILING),
        ("production_authority", PRODUCTION_AUTHORITY),
        ("protected_main_merge", PROTECTED_MAIN_MERGE),
        ("execution_authority", EXECUTION_AUTHORITY),
    ):
        if manifest.get(key) != expected:
            return {"status": "HOLD", "reason": f"{key.upper()}_WEAKENED"}
    if manifest.get("source_truth_preserved") is not True:
        return {"status": "HOLD", "reason": "SOURCE_TRUTH_NOT_PRESERVED"}
    if manifest.get("abstractive_summary_generated") is not False:
        return {"status": "HOLD", "reason": "ABSTRACTIVE_COMPACTION_FORBIDDEN_P0"}
    if manifest.get("dropped_resource_count") != 0:
        return {"status": "HOLD", "reason": "GOVERNED_RESOURCE_COVERAGE_LOST"}

    body = {k: v for k, v in manifest.items() if k != "compaction_digest"}
    if manifest.get("compaction_digest") != _digest(body):
        return {"status": "HOLD", "reason": "CONTEXT_COMPACTION_DIGEST_MISMATCH"}
    if manifest.get("selected_char_count", 0) > manifest.get("max_context_chars", 0):
        return {"status": "HOLD", "reason": "CONTEXT_BUDGET_EXCEEDED"}
    return {"status": "READY", "reason": "CONTEXT_COMPACTION_VALID"}

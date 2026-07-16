from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx

DATASET = Path(__file__).parents[1] / "evaluations" / "career_planning_cases.json"


@dataclass(slots=True)
class CaseResult:
    case_id: str
    passed: bool
    latency_ms: int
    failures: list[str]


def current_monday() -> date:
    today = date.today()
    return today - timedelta(days=today.weekday())


async def run_case(client: httpx.AsyncClient, case: dict[str, Any]) -> CaseResult:
    started = perf_counter()
    failures: list[str] = []
    profile = case["profile"]
    saved = await client.put("/v1/career/profile", json=profile)
    saved.raise_for_status()
    workspace_before = (await client.get("/v1/career")).json()
    previous_plan_id = (workspace_before.get("weekly_plan") or {}).get("id")
    allowed_questions = {item["id"] for item in workspace_before["question_options"]}
    owned_questions = {
        item["id"] for item in workspace_before["question_options"] if item["owned"]
    }
    week_start = current_monday()
    response = await client.post(
        "/v1/career/weekly-plan/draft", json={"week_start": week_start.isoformat()}
    )
    response.raise_for_status()
    draft = response.json()
    items = draft["items"]
    available = set(profile["available_weekdays"])
    if sum(item["estimated_minutes"] for item in items) > profile["weekly_hours"] * 60:
        failures.append("总时长超过画像预算")
    if any(date.fromisoformat(item["scheduled_date"]).weekday() not in available for item in items):
        failures.append("任务安排在不可训练星期")
    counts: dict[str, int] = {}
    for item in items:
        counts[item["scheduled_date"]] = counts.get(item["scheduled_date"], 0) + 1
        if item["question_id"] and item["question_id"] not in allowed_questions:
            failures.append("任务引用了候选列表外的题目")
        if item["task_type"] == "question_review" and not item["title"].startswith(
            ("精练 2 道", "精练 3 道")
        ):
            failures.append("题目精练任务没有明确 2 至 3 道题的题量")
        if not item["reason"] or not item["completion_criteria"]:
            failures.append("任务缺少推荐原因或完成标准")
    if any(count > 2 for count in counts.values()):
        failures.append("单日任务超过两项")
    if case["requires_owned_question"] and owned_questions and not any(
        item["question_id"] in owned_questions for item in items
    ):
        failures.append("存在个人题库时没有使用个人题")
    workspace_after = (await client.get("/v1/career")).json()
    after_plan_id = (workspace_after.get("weekly_plan") or {}).get("id")
    if after_plan_id != previous_plan_id:
        failures.append("未确认草稿改变了正式周计划")
    return CaseResult(
        case_id=case["id"],
        passed=not failures,
        latency_ms=round((perf_counter() - started) * 1000),
        failures=failures,
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description="运行求职训练规划 Skill 在线评测")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()
    token = os.getenv("EVAL_AUTH_TOKEN")
    if not token:
        parser.error("必须通过 EVAL_AUTH_TOKEN 提供测试账号令牌")
    payload = json.loads(args.dataset.read_text(encoding="utf-8"))
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(
        base_url=args.base_url.rstrip("/"), headers=headers, timeout=args.timeout
    ) as client:
        original = (await client.get("/v1/career")).json()["profile"]
        results: list[CaseResult] = []
        try:
            for case in payload["cases"]:
                try:
                    results.append(await run_case(client, case))
                except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
                    results.append(CaseResult(case["id"], False, 0, [type(exc).__name__]))
        finally:
            if original.get("confirmed_at"):
                restore = {
                    key: value
                    for key, value in original.items()
                    if key not in {"confirmed_at", "updated_at"}
                }
                await client.put("/v1/career/profile", json=restore)
            else:
                await client.delete("/v1/career/profile")
    summary = {
        "dataset_version": payload["dataset_version"],
        "total": len(results),
        "passed": sum(item.passed for item in results),
        "failed": sum(not item.passed for item in results),
        "average_latency_ms": round(sum(item.latency_ms for item in results) / len(results)),
        "cases": [asdict(item) for item in results],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

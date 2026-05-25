"""标书多轮精修服务 — 生成→审查→自动修复→再审查，3 轮闭合。"""
import json
import uuid
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from ..services.openai_service import OpenAIService
from ..services.knowledge_retrieval_service import KnowledgeRetrievalService


# ── helpers ──────────────────────────────────────────────────────────

ISSUE_SEVERITY_WEIGHT = {
    "critical": 20,
    "warning": 5,
    "info": 1,
}


def _compute_quality_score(issues: list[dict]) -> int:
    """根据 issue 数量和严重度计算质量分。"""
    score = 100
    for issue in issues:
        sev = str(issue.get("severity", "")).lower()
        weight = ISSUE_SEVERITY_WEIGHT.get(sev, 1)
        score -= weight
    return max(0, score)


def _count_by_severity(issues: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {"critical": 0, "warning": 0, "info": 0}
    for issue in issues:
        sev = str(issue.get("severity", "")).lower()
        if sev in counts:
            counts[sev] += 1
        else:
            counts["info"] += 1
    return counts


def _should_stop_early(issues: list[dict], prev_issue_count: int | None) -> tuple[bool, str]:
    """
    早停判定。

    Returns:
        (should_stop, reason)
    """
    counts = _count_by_severity(issues)

    # 条件 1：无 critical 且 warning < 3
    if counts["critical"] == 0 and counts["warning"] < 3:
        return True, "无严重问题且 warning 少于 3 个，提前结束"

    # 条件 2：连续两轮 issues 数不变
    current_count = len(issues)
    if prev_issue_count is not None and current_count == prev_issue_count:
        return True, f"连续两轮问题数不变（{current_count}），LLM 无法进一步改善"

    return False, ""


def _format_issues_as_suggestions(issues: list[dict]) -> list[str]:
    """将结构化 issue 列表转为 rewrite_chapter_with_suggestions 可用的建议列表。"""
    suggestions: list[str] = []
    for issue in issues:
        desc = str(issue.get("issue") or issue.get("description") or "").strip()
        suggestion = str(issue.get("suggestion") or "").strip()
        sev = str(issue.get("severity", "")).strip()

        prefix = f"[{sev}] " if sev else ""
        line = f"{prefix}{desc}"
        if suggestion:
            line += f" → 建议：{suggestion}"
        if line.strip():
            suggestions.append(line.strip())
    return suggestions


async def _parse_proofread_stream(stream: AsyncGenerator[str, None]) -> list[dict]:
    """将 proofread_chapter 的流式输出收集并解析为 issue 列表。"""
    collected = ""
    async for chunk in stream:
        collected += chunk

    if not collected.strip():
        return []

    try:
        result = json.loads(collected.strip())
        return result.get("issues", []) if isinstance(result, dict) else []
    except json.JSONDecodeError:
        # 尝试从文本中提取最后一个 JSON 块
        brace_start = collected.rfind("{")
        brace_end = collected.rfind("}")
        if brace_start >= 0 and brace_end > brace_start:
            try:
                snippet = collected[brace_start:brace_end + 1]
                result = json.loads(snippet)
                return result.get("issues", []) if isinstance(result, dict) else []
            except json.JSONDecodeError:
                pass
        return []


# ── pipeline ─────────────────────────────────────────────────────────

class RefinementService:
    """标书多轮精修管道。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute_refinement_pipeline(
        self,
        *,
        project_id: uuid.UUID,
        chapter: dict,
        chapter_rating_focus: str,
        chapter_role: str,
        adjacent_boundary: str,
        parent_chapters: list | None,
        sibling_chapters: list | None,
        project_overview: str,
        tech_requirements: str,
        project_response_matrix: str,
        knowledge_context: str,
        provider_config_id: str | None,
        model_name: str | None,
        max_rounds: int = 3,
        user_id: uuid.UUID | None = None,
    ) -> AsyncGenerator[dict, None]:
        """
        执行多轮精修管道，通过 SSE 事件流逐轮推送进度。

        Yields:
            dict: 每个事件，包含 type 和对应 data。
        """
        # ── 初始化 OpenAI 服务 ──
        openai_service = OpenAIService(db=self.db, project_id=project_id)
        if provider_config_id:
            configured = await openai_service.use_config_by_id(provider_config_id)
            if not configured:
                raise ValueError("所选 Provider 配置不存在")
        else:
            await openai_service._ensure_initialized()

        if not openai_service.api_key:
            raise ValueError("请先配置 AI 服务 API 密钥")

        if model_name:
            openai_service.set_model(model_name)

        # ── 知识库上下文 ──
        actual_knowledge = knowledge_context
        if not actual_knowledge:
            try:
                retrieval = KnowledgeRetrievalService(self.db)
                chapter_title = str(chapter.get("title") or chapter.get("id") or "")
                results = await retrieval.retrieve_for_chapter(
                    chapter_title=chapter_title,
                    chapter_description=str(chapter.get("description", "")),
                    project_overview=project_overview[:500],
                    user_id=user_id,
                    top_k=5,
                )
                if results:
                    actual_knowledge = "\n\n".join(
                        f"【{r.get('title', '参考')}】\n{r.get('content') or r.get('content_preview', '')}"
                        for r in results
                        if r.get("content") or r.get("content_preview")
                    )
            except Exception:
                pass

        # ── 响应矩阵 ──
        actual_response_matrix = project_response_matrix or openai_service._build_project_response_matrix([])

        # ── 章节信息 ──
        chapter_title = str(chapter.get("title") or chapter.get("id") or "未命名章节")

        # ── State ──
        current_content = ""
        total_issues_resolved = 0
        prev_issue_count: int | None = None

        for round_num in range(1, max_rounds + 1):
            # ── Round Start ──
            yield {"type": "round_start", "data": {"round": round_num, "phase": "generate"}}

            # ── Generate / Rewrite ──
            if round_num == 1:
                # Round 1: 首轮生成
                current_content = await openai_service.generate_chapter_content_collect(
                    chapter=chapter,
                    parent_chapters=parent_chapters,
                    sibling_chapters=sibling_chapters,
                    project_overview=project_overview,
                    knowledge_context=actual_knowledge,
                    tech_requirements=tech_requirements,
                    project_response_matrix=actual_response_matrix,
                    chapter_rating_focus=chapter_rating_focus,
                    chapter_role=chapter_role,
                    adjacent_boundary=adjacent_boundary,
                )
            else:
                # Round 2+: 按建议改写
                yield {"type": "progress", "data": {"round": round_num, "message": "正在按审查建议改写..."}}

                current_content = await openai_service.rewrite_chapter_with_suggestions(
                    chapter_title=chapter_title,
                    chapter_content=current_content,
                    suggestions=_format_issues_as_suggestions(all_issues),
                )

            if not current_content or not current_content.strip():
                yield {
                    "type": "error",
                    "data": {"round": round_num, "message": "内容生成失败，无法继续精修"},
                }
                return

            # ── Review ──
            yield {"type": "progress", "data": {"round": round_num, "message": "正在审查章节..."}}

            # 校对
            proofread_stream = openai_service.proofread_chapter(
                chapter_title=chapter_title,
                chapter_content=current_content,
                tech_requirements=tech_requirements,
                project_overview=project_overview,
            )
            all_issues = await _parse_proofread_stream(proofread_stream)

            counts = _count_by_severity(all_issues)

            # Round 1: 额外检查评分点覆盖
            if round_num == 1 and tech_requirements:
                try:
                    checklist_json = await openai_service.generate_rating_response_checklist(
                        overview=project_overview,
                        requirements=tech_requirements,
                    )
                    checklist = json.loads(checklist_json)
                    # 将 checklist 中的 risk_points 作为 info 级 issue 加入
                    for item in (checklist if isinstance(checklist, list) else checklist.get("items", [])):
                        for risk in item.get("risk_points", []):
                            all_issues.append({
                                "severity": "info",
                                "category": "coverage",
                                "position": str(item.get("rating_item", "评分项")),
                                "issue": str(risk),
                                "suggestion": "建议检查覆盖情况",
                            })
                except Exception:
                    pass  # 评分清单生成失败不阻塞流程

            # ── 推送 Issues ──
            yield {
                "type": "round_issues",
                "data": {
                    "round": round_num,
                    "issues": all_issues,
                    "counts": _count_by_severity(all_issues),
                },
            }

            # ── 早停检查 ──
            should_stop, stop_reason = _should_stop_early(all_issues, prev_issue_count)

            total_issues_resolved += prev_issue_count - len(all_issues) if prev_issue_count is not None else 0
            prev_issue_count = len(all_issues)

            # ── Round Complete ──
            yield {
                "type": "round_complete",
                "data": {
                    "round": round_num,
                    "phase": "review",
                    "issues_found": len(all_issues),
                    "critical": counts["critical"],
                    "warning": counts["warning"],
                    "info": counts["info"],
                    "early_stop": should_stop,
                    "stop_reason": stop_reason if should_stop else None,
                },
            }

            if should_stop and round_num < max_rounds:
                break

            if round_num >= max_rounds:
                break

        # ── 最终质量评分 ──
        quality_score = _compute_quality_score(all_issues)
        needs_review = quality_score < 60

        yield {
            "type": "refine_complete",
            "data": {
                "final_content": current_content,
                "total_rounds": min(round_num, max_rounds),
                "total_issues": len(all_issues),
                "issues_resolved": total_issues_resolved,
                "quality_score": quality_score,
                "needs_manual_review": needs_review,
                "final_issue_counts": counts,
            },
        }

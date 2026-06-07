from dataclasses import dataclass
from pathlib import Path

from core.paths import AGENT_SKILLS_DIR


@dataclass(frozen=True, slots=True)
class AgentSkillSummary:
    """LLM instructions에 노출할 agent skill 요약 정보입니다."""

    name: str
    title: str
    description: str


def load_agent_skill_catalog() -> str:
    """프로젝트 agent skill 목록과 간략한 설명을 Markdown으로 구성합니다."""
    summaries = list_agent_skill_summaries()
    if not summaries:
        return "현재 사용할 수 있는 프로젝트 skill이 없습니다."

    lines = [
        "필요한 경우 `load_agent_skill` tool로 skill 전문을 읽은 뒤 해당 지침을 따르세요.",
        "",
    ]
    lines.extend(
        f"- `{summary.name}` ({summary.title}): {summary.description}"
        for summary in summaries
    )
    return "\n".join(lines)


def list_agent_skill_summaries() -> list[AgentSkillSummary]:
    """skills 디렉터리의 Markdown 문서에서 skill 요약 목록을 로드합니다."""
    if not AGENT_SKILLS_DIR.exists():
        return []

    summaries: list[AgentSkillSummary] = []
    for skill_path in sorted(AGENT_SKILLS_DIR.glob("*.md")):
        if not skill_path.is_file():
            continue
        content = skill_path.read_text(encoding="utf-8").strip()
        summaries.append(_build_skill_summary(skill_path, content))
    return summaries


def load_agent_skill(skill_name: str) -> tuple[AgentSkillSummary, str]:
    """skill 이름으로 단일 skill Markdown 전문을 로드합니다."""
    skill_path = _resolve_skill_path(skill_name)
    content = skill_path.read_text(encoding="utf-8").strip()
    return _build_skill_summary(skill_path, content), content


def load_agent_skills() -> str:
    """프로젝트 agent skill 문서를 하나의 instructions 조각으로 로드합니다.

    이전 런타임 호환을 위해 유지하며, 신규 instructions에서는 catalog와
    `load_agent_skill` tool 조합을 사용합니다.
    """
    if not AGENT_SKILLS_DIR.exists():
        return ""

    skill_sections = [
        skill_path.read_text(encoding="utf-8").strip()
        for skill_path in sorted(AGENT_SKILLS_DIR.glob("*.md"))
        if skill_path.is_file()
    ]
    return "\n\n".join(section for section in skill_sections if section)


def _resolve_skill_path(skill_name: str) -> Path:
    """catalog에 노출된 skill 이름만 파일 경로로 변환합니다."""
    normalized_name = skill_name.strip()
    if not normalized_name:
        raise ValueError("skill_name is required.")

    for summary in list_agent_skill_summaries():
        if summary.name == normalized_name:
            return AGENT_SKILLS_DIR / f"{summary.name}.md"

    raise ValueError(f"Unknown skill: {skill_name}")


def _build_skill_summary(skill_path: Path, content: str) -> AgentSkillSummary:
    """Markdown 제목과 첫 설명 문단으로 skill catalog 항목을 만듭니다."""
    title = _extract_skill_title(content) or skill_path.stem
    description = _extract_skill_description(content) or "추가 설명이 없습니다."
    return AgentSkillSummary(
        name=skill_path.stem,
        title=title,
        description=description,
    )


def _extract_skill_title(content: str) -> str | None:
    """첫 번째 H1 제목에서 skill 표시명을 추출합니다."""
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("# "):
            continue
        title = stripped.removeprefix("# ").strip()
        return title.removeprefix("Skill:").strip() or title
    return None


def _extract_skill_description(content: str) -> str | None:
    """제목 직후의 첫 일반 문단을 catalog 설명으로 사용합니다."""
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return " ".join(stripped.split())
    return None

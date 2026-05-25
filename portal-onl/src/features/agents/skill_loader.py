from core.paths import AGENT_SKILLS_DIR


def load_agent_skills() -> str:
    """프로젝트 agent skill 문서를 하나의 instructions 조각으로 로드합니다."""
    if not AGENT_SKILLS_DIR.exists():
        return ""

    skill_sections = [
        skill_path.read_text(encoding="utf-8").strip()
        for skill_path in sorted(AGENT_SKILLS_DIR.glob("*.md"))
        if skill_path.is_file()
    ]
    return "\n\n".join(section for section in skill_sections if section)

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from core.paths import AGENT_PROMPTS_DIR


_PROMPT_ENV = Environment(
    loader=FileSystemLoader(AGENT_PROMPTS_DIR),
    autoescape=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_prompt(template_name: str, **context: object) -> str:
    template = _PROMPT_ENV.get_template(template_name)
    return template.render(**context).strip()


def load_markdown_prompt(file_name: str) -> str:
    return _read_prompt_file(file_name, expected_suffix=".md")


def load_text_prompt(file_name: str) -> str:
    return _read_prompt_file(file_name, expected_suffix=".txt")


def load_prompt(file_name: str, **context: object) -> str:
    suffix = Path(file_name).suffix.lower()
    if suffix == ".j2":
        return render_prompt(file_name, **context)
    if suffix == ".md":
        return load_markdown_prompt(file_name)
    if suffix == ".txt":
        return load_text_prompt(file_name)
    raise ValueError(f"Unsupported prompt file type: {file_name}")


def _read_prompt_file(file_name: str, *, expected_suffix: str) -> str:
    prompt_path = AGENT_PROMPTS_DIR / file_name
    if prompt_path.suffix.lower() != expected_suffix:
        raise ValueError(f"Expected {expected_suffix} prompt file, got: {file_name}")
    return prompt_path.read_text(encoding="utf-8").strip()

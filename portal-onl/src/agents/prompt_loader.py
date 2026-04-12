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

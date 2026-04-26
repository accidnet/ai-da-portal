from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]

SRC_DIR = ROOT_DIR / "src"
DATA_DIR = ROOT_DIR / "data"
UPLOADED_DATASETS_DIR = DATA_DIR / "uploaded_datasets"

AGENTS_DIR = SRC_DIR / "agents"
AGENT_PROMPTS_DIR = AGENTS_DIR / "prompts"

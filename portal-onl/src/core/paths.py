from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]

SRC_DIR = ROOT_DIR / "src"
DATA_DIR = ROOT_DIR / "data"
UPLOADED_DATASET_DIR = DATA_DIR / "attached_datasets"
DATA_SOURCE_STORAGE_DIR = DATA_DIR / "data_sources"

AGENTS_DIR = SRC_DIR / "features" / "agents"
AGENT_PROMPTS_DIR = AGENTS_DIR / "prompts"

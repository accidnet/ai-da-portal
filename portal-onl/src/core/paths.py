from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]

# root sub dir
SRC_DIR = ROOT_DIR / "src"
DATA_DIR = ROOT_DIR / "data"
LOG_DIR = ROOT_DIR / "logs"

# data sub dir
UPLOADED_DATASET_DIR = DATA_DIR / "attached_datasets"
DATA_SOURCE_STORAGE_DIR = DATA_DIR / "data_sources"
WORKSPACE_STORAGE_DIR = DATA_DIR / "workspaces"

AGENTS_DIR = SRC_DIR / "features" / "agents"
AGENT_PROMPTS_DIR = AGENTS_DIR / "prompts"

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
USER_DATA_DIR = BASE_DIR / "user_data"
UPLOADS_DIR = USER_DATA_DIR / "uploads"
DB_PATH = BASE_DIR / "db" / "app.db"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
(BASE_DIR / "db").mkdir(exist_ok=True)

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "siliconflow")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-V3")

LLM_BASE_URLS = {
    "aliyun": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "siliconflow": "https://api.siliconflow.cn/v1",
}
LLM_BASE_URL = LLM_BASE_URLS.get(LLM_PROVIDER, LLM_BASE_URLS["siliconflow"])

APP_SECRET_KEY = os.getenv("APP_SECRET_KEY", "dev-secret-key-change-in-prod")

APP_NAME = "QuantResearch Assistant"
APP_VERSION = "1.0.0"

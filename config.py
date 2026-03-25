from dotenv import load_dotenv
import os

load_dotenv()

ERPNEXT_URL = os.getenv("ERPNEXT_URL", "http://localhost:8000")
ERPNEXT_API_KEY = os.getenv("ERPNEXT_API_KEY", "")
ERPNEXT_API_SECRET = os.getenv("ERPNEXT_API_SECRET", "")
LM_STUDIO_URL = os.getenv("LM_STUDIO_URL", "http://127.0.0.1:1234")
LM_STUDIO_MODEL = os.getenv("LM_STUDIO_MODEL", "qwen/qwen3.5-9b")
FASTAPI_PORT = int(os.getenv("FASTAPI_PORT", "8080"))

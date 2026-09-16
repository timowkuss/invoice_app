"""Server configuration. Secrets must never be serialized to clients."""
import os
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
DATA_DIR = Path(os.getenv('DATA_DIR', str(ROOT / 'data'))).resolve()
UPLOAD_DIR = DATA_DIR / 'uploads'
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{DATA_DIR / "invoice.db"}')
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_PAGES = 30

def secret_key():
    key = os.getenv('SECRET_KEY', '')
    if len(key) < 32 or key.startswith('change-this'):
        raise RuntimeError('Set a random SECRET_KEY of at least 32 characters in .env')
    return key

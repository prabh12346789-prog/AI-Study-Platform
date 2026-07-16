import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND)); os.chdir(BACKEND); load_dotenv(BACKEND / ".env")

from src.current_affairs.service import CurrentAffairsService

if __name__ == "__main__":
    print(json.dumps(CurrentAffairsService().reindex_active()))

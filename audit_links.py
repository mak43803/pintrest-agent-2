"""
Audit Links CLI — Standalone tool to verify all Pinterest & Linktree affiliate links.
========================================================================================

Run:
    python audit_links.py
"""

import sys
import os
from pathlib import Path

# Force UTF-8 encoding for Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from database.database import Database
from database.init_db import create_database
from utils.link_auditor import LinkAuditorBot
from utils.logger import setup_logging

def main():
    setup_logging()
    db_path = Path("database/pinterest_ai_agent.db")
    
    if not db_path.exists():
        print(f"❌ Database file not found at '{db_path}'. Has the agent published any pins yet?")
        return

    print("🚀 Initializing Affiliate Link Audit Bot...")
    db = Database(str(db_path))
    create_database(db)

    bot = LinkAuditorBot(db)
    results = bot.audit_all_products()

    db.close()

if __name__ == "__main__":
    main()

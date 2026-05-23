"""
Script that teaches GLIA about the example project.

Run from the example_project directory:
    python teach_glia.py

This simulates what a developer would do when onboarding GLIA
to understand their codebase. Each 'learn' call feeds a file
or piece of knowledge to the distiller.
"""

import sys
from pathlib import Path

# Add GLIA src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import os
from glia.brain import GliaBrain

# Initialize GLIA in this project directory
workspace = Path(__file__).parent
brain = GliaBrain(
    workspace=workspace,
    api_key=os.environ.get("GEMINI_API_KEY"),
    model=os.environ.get("GLIA_MODEL", "gemini-3.1-flash-lite-preview"),
)

if not brain.is_initialized:
    brain.init()
    print("🧠 GLIA initialized in example_project/")

# --- Teach GLIA about each file ---

files_to_learn = [
    "src/app.py",
    "src/auth.py",
    "src/database.py",
    "src/models.py",
]

for filepath in files_to_learn:
    full_path = workspace / filepath
    if full_path.exists():
        content = full_path.read_text(encoding="utf-8")
        print(f"\n📄 Teaching: {filepath}")
        try:
            result = brain.learn(content, source=filepath)
            concepts = result.get("concepts", [])
            print(f"   ✅ Concepts: {', '.join(concepts)}")
            print(f"   📝 Summary: {result.get('summary', '')}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

# --- Teach some project-specific knowledge ---

extra_knowledge = [
    {
        "content": "There was a critical bug where tokens expired immediately because "
                   "the expiration was calculated in milliseconds instead of seconds. "
                   "Fixed in auth.py line 25 by changing time.time() * 1000 to time.time(). "
                   "This caused all user sessions to drop after login.",
        "source": "bug-fix/issue-42",
    },
    {
        "content": "The API uses SQLite for development but PostgreSQL in production. "
                   "The DATABASE_PATH env var controls which database file is used. "
                   "In production, this is overridden by the DATABASE_URL connection string.",
        "source": "docs/deployment.md",
    },
    {
        "content": "Priority levels for tasks are: low, medium, high, critical. "
                   "Critical tasks trigger a webhook notification to Slack via the "
                   "SLACK_WEBHOOK_URL environment variable.",
        "source": "docs/features.md",
    },
]

for knowledge in extra_knowledge:
    print(f"\n💡 Teaching: {knowledge['source']}")
    try:
        result = brain.learn(knowledge["content"], source=knowledge["source"])
        concepts = result.get("concepts", [])
        print(f"   ✅ Concepts: {', '.join(concepts)}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

# --- Show final stats ---
print("\n" + "=" * 50)
stats = brain.stats()
print(f"📊 GLIA learned about this project:")
print(f"   Nodes (concepts):    {stats['nodes']}")
print(f"   Edges (connections): {stats['edges']}")
print(f"   Threads (memories):  {stats['threads']}")
print("=" * 50)
print("\n🎉 Done! Now try:")
print("   python -m glia recall \"auth\"")
print("   python -m glia recall \"bug\"")
print("   python -m glia recall \"database\"")
print("   python -m glia recall \"token expiration\"")

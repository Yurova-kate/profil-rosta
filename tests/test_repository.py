from pathlib import Path

def test_required_architecture_documents_exist():
    root = Path(__file__).resolve().parents[1]
    for path in ("README.md", "docs/ARCHITECTURE.md", "docs/ROADMAP.md"):
        assert (root / path).is_file()

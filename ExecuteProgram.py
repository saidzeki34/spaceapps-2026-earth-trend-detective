"""Launch the one Streamlit application with this Python environment."""
import subprocess
import sys
from pathlib import Path


def main() -> int:
    app = Path(__file__).resolve().with_name("streamlit_app.py")
    return subprocess.call([sys.executable, "-m", "streamlit", "run", str(app), *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())

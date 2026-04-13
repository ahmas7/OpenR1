"""
Launch the R1 GUI
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from R1.gui import run_gui

if __name__ == "__main__":
    print("=" * 50)
    print("  R1 Assistant - Desktop GUI")
    print("=" * 50)
    print()

    # Try to connect to runtime, otherwise run standalone
    runtime = None
    try:
        from R1.agent import get_runtime
        runtime = get_runtime()
        print("Connected to R1 runtime")
    except Exception as e:
        print(f"Running in standalone mode (runtime unavailable: {e})")

    run_gui(runtime=runtime)

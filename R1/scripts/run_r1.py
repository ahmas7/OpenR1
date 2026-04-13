"""
R1 Launcher - Self-Improving AI
Run this to start R1
"""
import sys
import os

# Add parent directory (project root) to path so R1 package can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if __name__ == "__main__":
    print("="*50)
    print("  ORION-R1 (Self-Improving AI)")
    print("  http://localhost:8000")
    print("="*50)
    
    import uvicorn
    from R1.api.server import app
    
    # Run on localhost (not 0.0.0.0)
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)

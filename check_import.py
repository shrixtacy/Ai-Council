
import sys
import os
sys.path.insert(0, os.getcwd())
try:
    import web_app.backend.main
    print("Import successful")
except ImportError as e:
    print(f"Import failed: {e}")
except Exception as e:
    print(f"Error: {e}")

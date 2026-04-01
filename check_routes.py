import sys
import os

# Add the parent directory to sys.path so we can import 'app'
sys.path.append(os.getcwd())

from app.main import app

print("Listing all registered routes:")
for route in app.routes:
    if hasattr(route, "methods"):
        print(f"{route.path} {route.methods}")
    else:
        print(f"{route.path} (Mount/Other)")

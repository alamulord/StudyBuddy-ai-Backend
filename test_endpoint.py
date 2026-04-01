import sys
import os

sys.path.append(os.getcwd())

try:
    from fastapi.testclient import TestClient
    from app.main import app
    
    client = TestClient(app)
    
    with open("result.txt", "w") as f:
        f.write("Testing DELETE request...\n")
        # Using a fake ID
        response = client.delete("/api/v1/materials/12345")
        f.write(f"DELETE /api/v1/materials/12345 -> Status: {response.status_code}\n")
        
        f.write("\nListing Material Routes:\n")
        for route in app.routes:
            if hasattr(route, "path") and "/materials" in route.path:
                f.write(f"{route.path} {route.methods}\n")

except Exception as e:
    with open("result.txt", "w") as f:
        f.write(f"Error: {e}")

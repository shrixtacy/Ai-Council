
import subprocess
import sys
import time
import urllib.request
import urllib.error
import os

def check_cors():
    # Start the backend server
    # Assuming python is in path and has dependencies installed. 
    # If not, this might fail, but we'll try to use sys.executable.
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "web_app.backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd="d:/OSCG/aic/Ai-Council",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    print("Starting server...")
    time.sleep(10)  # Wait for server to start

    try:
        # Test with an arbitrary origin
        origin = "http://evil.com"
        req = urllib.request.Request(
            "http://127.0.0.1:8000/api/status",
            headers={
                "Origin": origin, 
                "Access-Control-Request-Method": "GET"
            },
            method="OPTIONS"
        )
        
        with urllib.request.urlopen(req) as response:
            acao = response.headers.get("Access-Control-Allow-Origin")
            print(f"Request Origin: {origin}")
            print(f"Access-Control-Allow-Origin: {acao}")

            if acao == "*":
                print("VULNERABLE: Wildcard origin allowed.")
            elif acao == origin:
                 print(f"VULNERABLE: Origin {origin} explicitly allowed (or reflected).")
            else:
                print(f"SECURE: Origin not allowed (ACAO: {acao}).")

    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} {e.reason}")
        print(f"Headers: {e.headers}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        process.terminate()
        # Read stdout/stderr for debugging
        stdout, stderr = process.communicate()
        if stdout: print(f"Server STDOUT:\n{stdout.decode(errors='ignore')}")
        if stderr: print(f"Server STDERR:\n{stderr.decode(errors='ignore')}")

if __name__ == "__main__":
    check_cors()

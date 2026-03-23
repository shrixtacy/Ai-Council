import subprocess
import sys

def run_tests():
    cmd = [
        sys.executable, "-m", "pytest", 
        "tests/test_synthesis_extended.py", 
        "--cov=ai_council.synthesis.layer", 
        "--cov-report=term-missing"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    
    with open("test_synthesis_extended_utf8.txt", "w", encoding="utf-8") as f:
        f.write(result.stdout)
        f.write("\n\nERRORS:\n")
        f.write(result.stderr)
    
    print(f"Finished with exit code {result.returncode}")

if __name__ == "__main__":
    run_tests()

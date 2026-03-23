import subprocess
import sys
import argparse

def run_tests(output_path: str):
    cmd = [
        sys.executable, "-m", "pytest", 
        "tests/test_arbitration_extended.py", 
        "--cov=ai_council.arbitration.layer", 
        "--cov-report=term-missing"
    ]
    print(f"Running arbitration tests, output will be saved to {output_path}...")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result.stdout)
        f.write("\n\nERRORS:\n")
        f.write(result.stderr)
    
    print(f"Finished with exit code {result.returncode}")
    sys.exit(result.returncode)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run arbitration tests and generate report.")
    parser.add_argument("--output", type=str, default="test_arbitration_extended_utf8.txt", help="Path to the output report file.")
    args = parser.parse_args()
    
    run_tests(args.output)

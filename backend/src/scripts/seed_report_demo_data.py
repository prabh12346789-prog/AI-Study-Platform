import sys
import os

def main():
    clear = "--clear" in sys.argv
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")
    
    # Read existing env content
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            lines = f.readlines()
            
    # Update or add REPORT_DEMO_MODE
    new_lines = []
    found = False
    for line in lines:
        if line.strip().startswith("REPORT_DEMO_MODE="):
            new_lines.append(f"REPORT_DEMO_MODE={'false' if clear else 'true'}\n")
            found = True
        else:
            new_lines.append(line)
            
    if not found:
        new_lines.append(f"REPORT_DEMO_MODE={'false' if clear else 'true'}\n")
        
    # Write back to .env
    with open(env_path, "w") as f:
        f.writelines(new_lines)
        
    if clear:
        print("Report Demo Mode successfully disabled and cleared.")
    else:
        print("Report Demo Mode successfully enabled for demonstration.")

if __name__ == "__main__":
    main()

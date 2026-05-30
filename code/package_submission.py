import os
import sys
import zipfile

def should_exclude(path):
    excludes = ["__pycache__", "venv", ".env", "node_modules", "data", "chroma_db", ".git"]
    parts = path.replace("\\", "/").split("/")
    for excl in excludes:
        if excl in parts or path.endswith(excl):
            return True
    return False

def package_submission():
    zip_name = "submission.zip"
    # Determine paths
    base_dir = os.path.dirname(os.path.abspath(__file__)) # this is 'code'
    parent_dir = os.path.dirname(base_dir) # hackerrank-orchestrate-may26
    
    if sys.platform.startswith('win'):
        log_path = os.path.join(os.environ.get('USERPROFILE', ''), 'hackerrank_orchestrate', 'log.txt')
    else:
        log_path = os.path.join(os.environ.get('HOME', ''), 'hackerrank_orchestrate', 'log.txt')
        
    output_path = os.path.join(parent_dir, "support_tickets", "output.csv")
    zip_path = os.path.join(parent_dir, zip_name)
    
    print(f"Creating {zip_name}...")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # 1. Add code directory
        for root, dirs, files in os.walk(base_dir):
            if should_exclude(root):
                continue
            for file in files:
                file_path = os.path.join(root, file)
                if should_exclude(file_path):
                    continue
                # Store relative to parent so it becomes 'code/...'
                arcname = os.path.relpath(file_path, parent_dir)
                zipf.write(file_path, arcname)
                print(f"Added: {arcname}")
                
        # 2. Add output.csv
        if os.path.exists(output_path):
            zipf.write(output_path, "output.csv")
            print(f"Added: output.csv from {output_path}")
        else:
            print(f"Warning: {output_path} not found. Ensure pipeline is run first.")
            
        # 3. Add log.txt
        if os.path.exists(log_path):
            zipf.write(log_path, "log.txt")
            print(f"Added: log.txt from {log_path}")
        else:
            print(f"Warning: {log_path} not found.")
            
    print(f"\nSuccessfully created {zip_path}")

if __name__ == "__main__":
    package_submission()

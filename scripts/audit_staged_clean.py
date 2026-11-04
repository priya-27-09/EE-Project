import os
import subprocess
import sys

def main():
    result = subprocess.run(["git", "diff", "--cached", "--name-only"], capture_output=True, text=True, check=True)
    files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    print(f"Total staged files: {len(files)}")
    
    large_files = []
    suspicious = []
    file_sizes = []
    
    for f in files:
        if os.path.exists(f):
            sz = os.path.getsize(f)
            sz_mb = sz / (1024 * 1024)
            file_sizes.append((f, sz_mb))
            if sz > 50 * 1024 * 1024:
                large_files.append((f, sz_mb))
        else:
            print(f"WARNING: File {f} does not exist on disk!")
            
        lower_f = f.lower()
        if lower_f.startswith(".env") and not (lower_f.endswith(".example") or lower_f.endswith(".render.example")):
            suspicious.append(f)
        if any(bad in lower_f for bad in ["password", "secret", "credential"]) and not any(ok in lower_f for ok in ["example", "test", "schema", "auth", "audit", "blockchain"]):
            suspicious.append(f)
        if lower_f.endswith(".pem") or lower_f.endswith(".pfx") or lower_f.endswith(".key"):
            suspicious.append(f)
        if lower_f.endswith(".sqlite") or lower_f.endswith(".db"):
            suspicious.append(f)

    print(f"\nFiles exceeding 50 MB limit: {len(large_files)}")
    for f, sz in large_files:
        print(f"  EXCEEDS LIMIT: {f} ({sz:.2f} MB)")
        
    print(f"\nSuspicious security/credential files: {len(suspicious)}")
    for f in suspicious:
        print(f"  SUSPICIOUS: {f}")
        
    file_sizes.sort(key=lambda x: x[1], reverse=True)
    print("\nTop 15 largest staged files:")
    for f, sz in file_sizes[:15]:
        print(f"  {sz:6.2f} MB : {f}")

if __name__ == "__main__":
    main()


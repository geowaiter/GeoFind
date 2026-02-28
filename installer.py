import subprocess
import sys

def setup():
    pkgs = ["flask", "flask-cors", "requests", "Pillow", "torch", "torchvision", "geoclip"]
    
    print("\nGeoFIND // System Setup\n" + "-"*30)
    print(f"Installing: {', '.join(pkgs)}")

    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", *pkgs],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT
        )
        print("\n[+] Environment Ready.\nRun 'python run.py' to begin.")
    except Exception:
        print("\n[!] Setup failed. Check network/permissions.")
        sys.exit(1)

if __name__ == "__main__":
    setup()

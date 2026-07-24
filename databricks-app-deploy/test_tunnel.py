import os
import subprocess
import urllib.request
import threading
import time

def test_tunnel():
    CLOUDFLARED_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    CLOUDFLARED_PATH = "cloudflared.exe"
    TOKEN = "eyJhIjoiMTE2YzQyZDEyNDg5MjA3YmYzMjAzYzEzZWFjODQyNjAiLCJ0IjoiNDdhZGVmMmMtMDllZi00YWJjLWFlNDEtMjcwN2FlYjEyYWZhIiwicyI6IllUYzBNRE5pT0dJdFpHVmhZaTAwWlRZM0xXSmtaVFl0WVdReFpERTBaVGcxWldWaiJ9"

    try:
        if not os.path.exists(CLOUDFLARED_PATH):
            print("Downloading cloudflared for Windows...")
            urllib.request.urlretrieve(CLOUDFLARED_URL, CLOUDFLARED_PATH)
        
        print("Starting cloudflared...")
        process = subprocess.Popen(
            [CLOUDFLARED_PATH, "tunnel", "--no-autoupdate", "run", "--token", TOKEN],
            stdout=open('cf_out.log', 'w'),
            stderr=subprocess.STDOUT
        )
        time.sleep(10)
        process.terminate()
        print("Done.")
            
    except Exception as e:
        print(f"Failed to start tunnel: {e}")

test_tunnel()

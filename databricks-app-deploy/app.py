import sys
import json
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
import os
import threading
import subprocess
import re
import time

UPSTREAM = 'https://opencode.ai'
AUTH_KEY = 'sk-mimo'
TUNNEL_URL = "隧道正在启动中，请稍后刷新..."

MODEL_MAP = {
    'deepseek-v4-flash': 'deepseek-v4-flash-free',
    'mimo-v2.5-pro': 'mimo-v2.5-free',
}

MODELS_LIST = {
    "object": "list",
    "data": [{"id": k, "object": "model", "created": 1700000000, "owned_by": "mimo"} for k in MODEL_MAP.keys()]
}

FAKE_PAGE = "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1.0'><title>Forever Proxy (Databricks App)</title><style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0a;color:#e0e0e0;min-height:100vh;display:flex;align-items:center;justify-content:center}.card{background:linear-gradient(135deg,#1a1a2e,#16213e);border:1px solid #333;border-radius:16px;padding:48px;max-width:520px;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.5)}h1{font-size:28px;background:linear-gradient(90deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:16px}p{color:#999;line-height:1.8;font-size:14px}.badge{display:inline-block;background:#667eea22;color:#667eea;border:1px solid #667eea44;padding:4px 12px;border-radius:20px;font-size:12px;margin-top:20px}</style></head><body><div class='card'><h1>Forever Proxy (Databricks App)</h1><p>高速稳定的 AI API 中转服务<br>支持 OpenAI / Claude / DeepSeek 全系列模型</p><span class='badge'>🔒 仅限授权用户</span></div></body></html>".encode('utf-8')

CORS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization, x-api-key',
}

TUNNEL_LOGS = []

import platform

def start_tunnel(port):
    global TUNNEL_URL, TUNNEL_LOGS
    system = platform.system().lower()
    if system == 'windows':
        CLOUDFLARED_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
        CLOUDFLARED_PATH = os.path.join(os.getcwd(), "cloudflared.exe")
    else:
        CLOUDFLARED_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
        CLOUDFLARED_PATH = os.path.join(os.getcwd(), "cloudflared")
        
    TOKEN = "eyJhIjoiMTE2YzQyZDEyNDg5MjA3YmYzMjAzYzEzZWFjODQyNjAiLCJ0IjoiNDdhZGVmMmMtMDllZi00YWJjLWFlNDEtMjcwN2FlYjEyYWZhIiwicyI6IllUYzBNRE5pT0dJdFpHVmhZaTAwWlRZM0xXSmtaVFl0WVdReFpERTBaVGcxWldWaiJ9"

    try:
        if not os.path.exists(CLOUDFLARED_PATH):
            TUNNEL_LOGS.append("Downloading cloudflared...")
            urllib.request.urlretrieve(CLOUDFLARED_URL, CLOUDFLARED_PATH)
            if system != 'windows':
                os.chmod(CLOUDFLARED_PATH, 0o755)

        # 启动固定隧道并捕获日志
        TUNNEL_LOGS.append("Starting cloudflared process...")
        process = subprocess.Popen(
            [CLOUDFLARED_PATH, "tunnel", "--no-autoupdate", "run", "--token", TOKEN],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        TUNNEL_URL = "https://opencode.sub2.kdns.fr"
        
        # 实时读取日志
        for line in process.stdout:
            TUNNEL_LOGS.append(line.strip())
            # 限制内存占用，只保留最后 200 行
            if len(TUNNEL_LOGS) > 200:
                TUNNEL_LOGS = TUNNEL_LOGS[-200:]
                
        TUNNEL_LOGS.append(f"Process exited with code {process.wait()}")
    except Exception as e:
        TUNNEL_URL = f"隧道启动失败: {str(e)}"
        TUNNEL_LOGS.append(f"EXCEPTION: {str(e)}")

class ProxyHTTPRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in CORS.items():
            self.send_header(k, v)
        self.end_headers()

    def handle_request(self):
        parsed_url = urlparse(self.path)
        
        # 0. 拦截 /logs 用于查看运行报错
        if parsed_url.path == '/logs':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            log_str = "\n".join(TUNNEL_LOGS) if TUNNEL_LOGS else "暂无日志"
            self.wfile.write(log_str.encode('utf-8'))
            return
            
        # 1. 拦截 /api 用于展示隧道地址
        if parsed_url.path == '/api':
            self.send_response(200)
            for k, v in CORS.items():
                self.send_header(k, v)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({"tunnel_url": TUNNEL_URL}, ensure_ascii=False, indent=2).encode('utf-8'))
            return
            
        # 2. 如果不是 /v1 开头，返回伪装界面
        if not parsed_url.path.startswith('/v1'):
            self.send_response(200)
            for k, v in CORS.items():
                self.send_header(k, v)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(FAKE_PAGE)
            return

        # 3. 鉴权逻辑
        auth = self.headers.get('Authorization', '')
        api_key = self.headers.get('x-api-key', '')
        if auth != f"Bearer {AUTH_KEY}" and api_key != AUTH_KEY:
            self.send_response(401)
            for k, v in CORS.items():
                self.send_header(k, v)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Unauthorized"}).encode('utf-8'))
            return

        # 4. 模型列表
        if parsed_url.path == '/v1/models':
            self.send_response(200)
            for k, v in CORS.items():
                self.send_header(k, v)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(MODELS_LIST).encode('utf-8'))
            return

        # 5. 请求重写与转发
        body = None
        if self.command == 'POST':
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                body_data = self.rfile.read(content_length)
                try:
                    data = json.loads(body_data.decode('utf-8'))
                    if 'model' in data and data['model'] in MODEL_MAP:
                        data['model'] = MODEL_MAP[data['model']]
                    body = json.dumps(data).encode('utf-8')
                except:
                    body = body_data

        upstream_url = f"{UPSTREAM}/zen{self.path}"
        req_headers = {}
        drop_headers = ['host', 'content-length', 'x-forwarded-for', 'x-real-ip', 'origin', 'referer', 'connection', 'accept-encoding', 'x-api-key']
        for k, v in self.headers.items():
            if k.lower() not in drop_headers:
                req_headers[k] = v
                
        req_headers['Authorization'] = 'Bearer public'
        req_headers['x-opencode-client'] = 'desktop'
        req_headers['Accept'] = 'text/event-stream'

        req = urllib.request.Request(upstream_url, data=body, headers=req_headers, method=self.command)

        try:
            with urllib.request.urlopen(req) as response:
                self.send_response(response.status)
                for k, v in CORS.items():
                    self.send_header(k, v)
                for k, v in response.headers.items():
                    if k.lower() not in ['transfer-encoding', 'connection', 'server', 'date']:
                        self.send_header(k, v)
                self.end_headers()

                while True:
                    chunk = response.read(4096)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            for k, v in CORS.items():
                self.send_header(k, v)
            for k, v in e.headers.items():
                if k.lower() not in ['transfer-encoding', 'connection']:
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Bad Gateway", "details": str(e)}).encode('utf-8'))

    def do_GET(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()

def run_server(server_port):
    server_address = ('0.0.0.0', server_port)
    httpd = ThreadingHTTPServer(server_address, ProxyHTTPRequestHandler)
    print(f'Starting Databricks App proxy on port {server_port}...')
    httpd.serve_forever()

if __name__ == '__main__':
    port = int(os.environ.get('DATABRICKS_APP_PORT', 8080))
    
    # 如果 Databricks 分配的端口不是 8080，我们必须额外在后台启动一个 8080 端口服务
    # 因为用户在 Cloudflare Dashboard 中把隧道写死了指向 8080 端口
    if port != 8080:
        threading.Thread(target=run_server, args=(8080,), daemon=True).start()

    # 启动 Cloudflare 隧道后台线程
    threading.Thread(target=start_tunnel, args=(port,), daemon=True).start()
    
    # 启动主 HTTP 服务器
    run_server(port)

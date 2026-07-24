# Databricks notebook source
# MAGIC %md
# MAGIC # OpenCode Proxy Server (内网穿透版)
# MAGIC 运行此单元格将启动一个监听在 8080 端口的 Python 代理服务器，并自动下载、配置并启动 Cloudflare Tunnel。
# MAGIC 启动成功后，您将在下方的输出日志中看到一个 `https://xxxx.trycloudflare.com` 格式的临时免费公网域名。
# MAGIC 您可以直接将该域名填入 NextChat 中使用！

# COMMAND ----------

import sys
import json
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
import threading
import subprocess
import os
import re
import time

# ==========================================
# 1. 代理服务器核心代码
# ==========================================
UPSTREAM = 'https://opencode.ai'
AUTH_KEY = 'sk-mimo'

MODEL_MAP = {
    'deepseek-v4-flash': 'deepseek-v4-flash-free',
    'mimo-v2.5-pro': 'mimo-v2.5-free',
}

MODELS_LIST = {
    "object": "list",
    "data": [{"id": k, "object": "model", "created": 1700000000, "owned_by": "mimo"} for k in MODEL_MAP.keys()]
}

FAKE_PAGE = b"<!DOCTYPE html><html lang='zh-CN'><head><meta charset='UTF-8'><title>Forever Proxy (Databricks)</title></head><body><h1>Forever Proxy Running on Cloudflare Tunnel</h1></body></html>"

CORS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization, x-api-key',
}

class ProxyHTTPRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # 禁用默认的请求日志输出，防止日志刷屏
        pass

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in CORS.items():
            self.send_header(k, v)
        self.end_headers()

    def handle_request(self):
        parsed_url = urlparse(self.path)
        
        if not parsed_url.path.startswith('/v1'):
            self.send_response(200)
            for k, v in CORS.items():
                self.send_header(k, v)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(FAKE_PAGE)
            return

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

        if parsed_url.path == '/v1/models':
            self.send_response(200)
            for k, v in CORS.items():
                self.send_header(k, v)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(MODELS_LIST).encode('utf-8'))
            return

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

# 在后台线程启动 HTTP 服务器
port = 8080
server_address = ('', port)
httpd = ThreadingHTTPServer(server_address, ProxyHTTPRequestHandler)
server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
server_thread.start()
print(f'✅ 本地 Python 代理服务器已在后台运行，端口: {port}')

# ==========================================
# 2. 自动下载并启动 Cloudflare Tunnel
# ==========================================
CLOUDFLARED_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
CLOUDFLARED_PATH = "/tmp/cloudflared"

if not os.path.exists(CLOUDFLARED_PATH):
    print("⏳ 正在下载 Cloudflare Tunnel 客户端...")
    urllib.request.urlretrieve(CLOUDFLARED_URL, CLOUDFLARED_PATH)
    os.chmod(CLOUDFLARED_PATH, 0o755)
    print("✅ 下载完成！")

print("⏳ 正在请求分配全球公网域名，请稍候...")
# 启动 cloudflared
process = subprocess.Popen(
    [CLOUDFLARED_PATH, "tunnel", "--url", f"http://127.0.0.1:{port}"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)

# 抓取生成的临时域名
url_found = False
url_pattern = re.compile(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com')

for line in process.stdout:
    match = url_pattern.search(line)
    if match:
        url = match.group(0)
        print("\n" + "="*60)
        print("🎉 恭喜！内网穿透成功！您的专属公网 API 代理地址为：")
        print(f"👉  {url}  👈")
        print("请将此链接复制到您的 NextChat 自定义接口地址中使用！")
        print("="*60 + "\n")
        print("⚠️ 提示：请不要关闭此单元格的运行状态，否则隧道会断开！")
        url_found = True
        break
    elif "error" in line.lower() or "failed" in line.lower():
        print(f"隧道日志: {line.strip()}")

if not url_found:
    print("❌ 获取公网域名失败，请重试或检查日志。")

# 保持主线程阻塞，防止单元格运行结束导致隧道中断
try:
    while True:
        time.sleep(60)
except KeyboardInterrupt:
    print("隧道已手动停止。")
    process.terminate()

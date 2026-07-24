import sys
import json
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

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

FAKE_PAGE = b"<!DOCTYPE html><html lang='zh-CN'><head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1.0'><title>Forever\xe4\xb8\xad\xe8\xbd\xac \xe2\x80\x94 \xe4\xbd\xbf\xe7\x94\xa8 TOKEN forever</title><style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0a;color:#e0e0e0;min-height:100vh;display:flex;align-items:center;justify-content:center}.card{background:linear-gradient(135deg,#1a1a2e,#16213e);border:1px solid #333;border-radius:16px;padding:48px;max-width:520px;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.5)}h1{font-size:28px;background:linear-gradient(90deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:16px}p{color:#999;line-height:1.8;font-size:14px}.badge{display:inline-block;background:#667eea22;color:#667eea;border:1px solid #667eea44;padding:4px 12px;border-radius:20px;font-size:12px;margin-top:20px}</style></head><body><div class='card'><h1>Forever \xe4\xb8\xad\xe8\xbd\xac\xe7\xab\x99 (Python)</h1><p>\xe9\xab\x98\xe9\x80\x9f\xe7\xa8\xb3\xe5\xae\x9a\xe7\x9a\x84 AI API \xe4\xb8\xad\xe8\xbd\xac\xe6\x9c\x8d\xe5\x8a\xa1<br>\xe6\x94\xaf\xe6\x8c\x81 OpenAI / Claude / DeepSeek \xe5\x85\xa8\xe7\xb3\xbb\xe5\x88\x97\xe6\xa8\xa1\xe5\x9e\x8b</p><span class='badge'>\xf0\x9f\x94\x92 \xe4\xbb\x85\xe9\x99\x90\xe6\x8e\x88\xe6\x9d\x83\xe7\x94\xa8\xe6\x88\xb7</span></div></body></html>"

CORS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization, x-api-key',
}

class ProxyHTTPRequestHandler(BaseHTTPRequestHandler):
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

def run(server_class=ThreadingHTTPServer, handler_class=ProxyHTTPRequestHandler, port=8080):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Starting Python proxy on port {port}...')
    httpd.serve_forever()

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8080))
    run(port=port)

const http = require('http');

const UPSTREAM = 'https://opencode.ai';
const AUTH_KEY = 'sk-mimo';

const MODEL_MAP = {
  'deepseek-v4-flash': 'deepseek-v4-flash-free',
  'mimo-v2.5-pro': 'mimo-v2.5-free',
};

const MODELS_LIST = {
  object: 'list',
  data: Object.keys(MODEL_MAP).map(id => ({
    id, object: 'model', created: Math.floor(Date.now() / 1000), owned_by: 'mimo',
  })),
};

const FAKE_PAGE = `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Forever中转 — 使用 TOKEN forever</title>
<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0a;color:#e0e0e0;min-height:100vh;display:flex;align-items:center;justify-content:center}
.card{background:linear-gradient(135deg,#1a1a2e,#16213e);border:1px solid #333;border-radius:16px;padding:48px;max-width:520px;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.5)}
h1{font-size:28px;background:linear-gradient(90deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:16px}
p{color:#999;line-height:1.8;font-size:14px}
.badge{display:inline-block;background:#667eea22;color:#667eea;border:1px solid #667eea44;padding:4px 12px;border-radius:20px;font-size:12px;margin-top:20px}</style></head>
<body><div class="card"><h1>Forever 中转站 (Galaxy Cloud)</h1><p>高速稳定的 AI API 中转服务<br>支持 OpenAI / Claude / DeepSeek 全系列模型</p><span class="badge">🔒 仅限授权用户</span></div></body></html>`;

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization, x-api-key',
};

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, \`http://\${req.headers.host || 'localhost'}\`);

  const setCORS = () => {
    for (const [k, v] of Object.entries(CORS)) {
      res.setHeader(k, v);
    }
  };

  if (req.method === 'OPTIONS') {
    res.writeHead(204, CORS);
    return res.end();
  }

  if (!url.pathname.startsWith('/v1')) {
    setCORS();
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    res.writeHead(200);
    return res.end(FAKE_PAGE);
  }

  const auth = req.headers['authorization'] || '';
  const apiKey = req.headers['x-api-key'] || '';
  if (auth !== \`Bearer \${AUTH_KEY}\` && apiKey !== AUTH_KEY) {
    setCORS();
    res.setHeader('Content-Type', 'application/json');
    res.writeHead(401);
    return res.end(JSON.stringify({ error: 'Unauthorized' }));
  }

  if (url.pathname === '/v1/models') {
    setCORS();
    res.setHeader('Content-Type', 'application/json');
    res.writeHead(200);
    return res.end(JSON.stringify(MODELS_LIST));
  }

  let bodyData = [];
  req.on('data', chunk => bodyData.push(chunk));
  req.on('end', async () => {
    let body = Buffer.concat(bodyData).toString();

    if (req.method === 'POST' && body) {
      try {
        const data = JSON.parse(body);
        if (data.model && MODEL_MAP[data.model]) {
          data.model = MODEL_MAP[data.model];
        }
        body = JSON.stringify(data);
      } catch {
        // Ignore parse errors
      }
    }

    const upstreamUrl = \`\${UPSTREAM}/zen\${url.pathname}\${url.search}\`;
    const upstreamHeaders = new Headers();

    const dropHeaders = ['host', 'content-length', 'x-forwarded-for', 'x-real-ip', 'origin', 'referer', 'connection', 'accept-encoding', 'x-api-key'];
    for (const [k, v] of Object.entries(req.headers)) {
      if (!dropHeaders.includes(k.toLowerCase())) {
        upstreamHeaders.set(k, v);
      }
    }

    upstreamHeaders.set('Authorization', 'Bearer public');
    upstreamHeaders.set('x-opencode-client', 'desktop');
    upstreamHeaders.set('Accept', 'text/event-stream');

    let init = {
      method: req.method,
      headers: upstreamHeaders,
    };
    if (req.method !== 'GET' && req.method !== 'HEAD') {
      init.body = body;
    }

    try {
      const resp = await fetch(upstreamUrl, init);

      setCORS();
      for (const [k, v] of resp.headers.entries()) {
        if (!['transfer-encoding', 'content-encoding', 'connection'].includes(k.toLowerCase())) {
          res.setHeader(k, v);
        }
      }
      res.writeHead(resp.status);

      if (resp.body) {
        for await (const chunk of resp.body) {
          res.write(chunk);
        }
      }
      res.end();
    } catch (err) {
      console.error(err);
      res.writeHead(502);
      res.end('Bad Gateway');
    }
  });
});

const port = process.env.PORT || 8080;
server.listen(port, () => {
  console.log(\`Galaxy proxy listening on port \${port}\`);
});

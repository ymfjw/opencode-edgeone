const UPSTREAM = 'https://opencode.ai';
const AUTH_KEY = 'sk-mimo';

const MODEL_MAP = {
  'hy3': 'hy3-free',
  'deepseek-v4-flash': 'deepseek-v4-flash-free',
  'deepseek-chat': 'deepseek-v4-flash-free',
  'deepseek-reasoner': 'deepseek-v4-flash-free',
  'deepseek-v3': 'deepseek-v4-flash-free',
  'deepseek-r1': 'deepseek-v4-flash-free',
  'mimo-v2.5-pro': 'mimo-v2.5-free',
  'mimo-v2.5': 'mimo-v2.5-free',
};

const MODELS_LIST = {
  object: 'list',
  data: Object.keys(MODEL_MAP).map(id => ({
    id, object: 'model', created: Math.floor(Date.now() / 1000), owned_by: 'mimo',
  })),
};

const FAKE_PAGE = `<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>OpenCode Wasmer Gateway</title>
<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0a;color:#e0e0e0;min-height:100vh;display:flex;align-items:center;justify-content:center}
.card{background:linear-gradient(135deg,#1a1a2e,#16213e);border:1px solid #333;border-radius:16px;padding:48px;max-width:520px;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.5)}
h1{font-size:28px;background:linear-gradient(90deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:16px}
p{color:#999;line-height:1.8;font-size:14px}
.badge{display:inline-block;background:#667eea22;color:#667eea;border:1px solid #667eea44;padding:4px 12px;border-radius:20px;font-size:12px;margin-top:20px}</style></head>
<body><div class="card"><h1>OpenCode Wasmer Gateway</h1><p>高速稳定的 AI API 中转服务 (Wasmer Edge)<br>支持 DeepSeek / MiMo / HunYuan 全系列模型</p><span class="badge">🔒 状态正常运行中</span></div></body></html>`;

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
  'Access-Control-Allow-Headers': 'Accept, Content-Type, Content-Length, Accept-Encoding, X-CSRF-Token, Authorization, x-api-key',
};

function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

function applyClientFingerprint(headers) {
  headers.set('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Opencode/1.0.8');
  headers.set('sec-ch-ua', '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"');
  headers.set('sec-ch-ua-mobile', '?0');
  headers.set('sec-ch-ua-platform', '"Windows"');
  headers.set('sec-fetch-dest', 'empty');
  headers.set('sec-fetch-mode', 'cors');
  headers.set('sec-fetch-site', 'cross-site');
  headers.set('Accept', 'application/json, text/event-stream, */*');
  headers.set('Accept-Language', 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7');
  headers.set('x-opencode-client', 'desktop');
  headers.set('x-opencode-version', '1.0.8');
  headers.set('Origin', 'https://opencode.ai');
  headers.set('Referer', 'https://opencode.ai/');

  const reqID = generateUUID();
  headers.set('x-opencode-session-id', generateUUID());
  headers.set('x-request-id', reqID);
  headers.set('x-correlation-id', reqID);
}

async function handleRequest(request) {
  try {
    const url = new URL(request.url);

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS });
    }

    if (!url.pathname.startsWith('/v1')) {
      return new Response(FAKE_PAGE, {
        headers: { 'Content-Type': 'text/html; charset=utf-8' },
      });
    }

    const auth = request.headers.get('Authorization') || '';
    const apiKey = request.headers.get('x-api-key') || '';
    if (auth !== `Bearer ${AUTH_KEY}` && apiKey !== AUTH_KEY) {
      return new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401, headers: { ...CORS, 'Content-Type': 'application/json' },
      });
    }

    if (url.pathname === '/v1/models' || url.pathname === '/models') {
      return new Response(JSON.stringify(MODELS_LIST), {
        headers: { ...CORS, 'Content-Type': 'application/json' },
      });
    }

    let body = null;
    let requestedModel = 'unknown';

    if (request.method !== 'GET' && request.method !== 'HEAD') {
      try {
        const text = await request.text();
        if (text) {
          const data = JSON.parse(text);
          if (data.model) {
            requestedModel = data.model;
            const m = data.model.toLowerCase();
            if (m === 'hy3') {
              data.model = 'hy3-free';
            } else if (m.startsWith('deepseek')) {
              data.model = 'deepseek-v4-flash-free';
            } else if (m.startsWith('mimo')) {
              data.model = 'mimo-v2.5-free';
            }
          }
          body = JSON.stringify(data);
        }
      } catch (e) {
        // Fallback
      }
    }

    let targetPath = url.pathname.startsWith('/v1/') ? '/zen' + url.pathname : (url.pathname.startsWith('/zen/') ? url.pathname : '/zen/v1/chat/completions');
    const upstreamUrl = `${UPSTREAM}${targetPath}${url.search}`;
    const upstreamHeaders = new Headers();
    
    const dropHeaders = ['host', 'content-length', 'x-forwarded-for', 'x-real-ip', 'origin', 'referer', 'connection', 'accept-encoding', 'x-api-key'];
    for (const [k, v] of request.headers.entries()) {
      if (!dropHeaders.includes(k.toLowerCase())) {
        upstreamHeaders.set(k, v);
      }
    }
    
    upstreamHeaders.set('Authorization', 'Bearer public');
    applyClientFingerprint(upstreamHeaders);

    let init = {
      method: request.method,
      headers: upstreamHeaders,
    };
    if (request.method !== 'GET' && request.method !== 'HEAD' && body) {
      init.body = body;
    }

    const resp = await fetch(upstreamUrl, init);

    const respHeaders = new Headers(resp.headers);
    Object.entries(CORS).forEach(([k, v]) => respHeaders.set(k, v));

    return new Response(resp.body, {
      status: resp.status,
      headers: respHeaders,
    });
  } catch (err) {
    return new Response(JSON.stringify({ error: String(err) }), {
      status: 500,
      headers: { ...CORS, 'Content-Type': 'application/json' },
    });
  }
}

addEventListener('fetch', (event) => {
  event.respondWith(handleRequest(event.request));
});

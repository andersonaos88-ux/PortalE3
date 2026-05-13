const CORS_ORIGINS = [
  'https://corretortech.com',
  'https://admin.corretortech.com',
  'https://api.corretortech.com',
  'https://www.corretortech.com',
];

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const method = request.method;
    const origin = request.headers.get('Origin') || '';

    if (method === 'OPTIONS') return corsResponse(null, 204, origin);

    const email = parseJwtEmail(request);

    // Normaliza path: /api/me → /me, /api/admin/... → /admin/...
    const path = url.pathname.replace(/^\/api/, '') || '/';

    try {
      // Debug endpoint (remover depois)
      if (path === '/debug' && method === 'GET') {
        const cookie = request.headers.get('Cookie') || '';
        const jwt = request.headers.get('CF-Access-Jwt-Assertion');
        const cfMatch = cookie.match(/CF_Authorization=([^;]+)/);
        return corsResponse({
          email,
          has_jwt_header: !!jwt,
          has_cf_cookie: !!cfMatch,
          cookie_keys: cookie.split(';').map(c => c.trim().split('=')[0]),
        }, 200, origin);
      }

      if (path === '/me' && method === 'GET')
        return handleMe(email, env, origin);

      if (path.startsWith('/admin'))
        return handleAdmin({ pathname: path }, method, request, email, env, origin);

      return corsResponse({ error: 'Not found' }, 404, origin);
    } catch (e) {
      return corsResponse({ error: e.message }, 500, origin);
    }
  },
};

/* ── Auth ─────────────────────────────────────────────── */

function parseJwtEmail(request) {
  // Tenta header (server-side Access)
  let jwt = request.headers.get('CF-Access-Jwt-Assertion');

  // Fallback: cookie CF_Authorization (browser fetch same-origin)
  if (!jwt) {
    const cookie = request.headers.get('Cookie') || '';
    const match = cookie.match(/CF_Authorization=([^;]+)/);
    if (match) jwt = match[1];
  }

  if (!jwt) return null;
  try {
    const payload = JSON.parse(atob(jwt.split('.')[1]));
    return payload.email || null;
  } catch { return null; }
}

async function isAdmin(email, env) {
  if (!email) return false;
  const admins = await env.KV.get('admins', 'json') || [];
  return admins.includes(email);
}

/* ── /me ──────────────────────────────────────────────── */

async function handleMe(email, env, origin) {
  if (!email) return corsResponse({ error: 'Não autenticado', cards: [] }, 401, origin);

  const user = await env.KV.get(`user:${email}`, 'json');
  if (!user || !user.ativo)
    return corsResponse({ error: 'Sem acesso', cards: [], bloqueado: true }, 403, origin);

  const plano = await env.KV.get(`plano:${user.plano}`, 'json');
  const allCards = await env.KV.get('cards', 'json') || [];
  const allowedIds = plano?.cards || [];
  const cards = allCards.filter(c => allowedIds.includes(c.id));
  const admin = await isAdmin(email, env);

  return corsResponse({ email, nome: user.nome, plano: user.plano, cards, admin });
}

/* ── /admin ───────────────────────────────────────────── */

async function handleAdmin(url, method, request, email, env, origin) {
  if (!await isAdmin(email, env))
    return corsResponse({ error: 'Acesso negado' }, 403, origin);

  const path = url.pathname.replace('/admin', '');

  /* --- Usuários --- */
  if (path === '/users' && method === 'GET') {
    const list = await env.KV.list({ prefix: 'user:' });
    const users = await Promise.all(
      list.keys.map(async k => {
        const u = await env.KV.get(k.name, 'json');
        return { email: k.name.replace('user:', ''), ...u };
      })
    );
    return corsResponse(users, 200, origin);
  }

  if (path === '/users' && method === 'POST') {
    const { email: ue, nome, plano, ativo = true } = await request.json();
    if (!ue || !plano) return corsResponse({ error: 'email e plano obrigatórios' }, 400, origin);
    const existing = await env.KV.get(`user:${ue}`, 'json') || {};
    await env.KV.put(`user:${ue}`, JSON.stringify({
      ...existing, nome, plano, ativo,
      criado: existing.criado || new Date().toISOString(),
      atualizado: new Date().toISOString(),
    }));
    return corsResponse({ ok: true }, 200, origin);
  }

  if (path.startsWith('/users/') && method === 'DELETE') {
    const ue = decodeURIComponent(path.replace('/users/', ''));
    await env.KV.delete(`user:${ue}`);
    return corsResponse({ ok: true }, 200, origin);
  }

  /* --- Planos --- */
  if (path === '/plans' && method === 'GET') {
    const list = await env.KV.list({ prefix: 'plano:' });
    const plans = await Promise.all(
      list.keys.map(async k => {
        const p = await env.KV.get(k.name, 'json');
        return { id: k.name.replace('plano:', ''), ...p };
      })
    );
    return corsResponse(plans, 200, origin);
  }

  if (path === '/plans' && method === 'POST') {
    const { id, label, cards } = await request.json();
    if (!id || !label) return corsResponse({ error: 'id e label obrigatórios' }, 400, origin);
    await env.KV.put(`plano:${id}`, JSON.stringify({ label, cards: cards || [] }));
    return corsResponse({ ok: true }, 200, origin);
  }

  if (path.startsWith('/plans/') && method === 'DELETE') {
    await env.KV.delete(`plano:${path.replace('/plans/', '')}`);
    return corsResponse({ ok: true }, 200, origin);
  }

  /* --- Cards --- */
  if (path === '/cards' && method === 'GET') {
    const cards = await env.KV.get('cards', 'json') || [];
    return corsResponse(cards, 200, origin);
  }

  if (path === '/cards' && method === 'POST') {
    const body = await request.json();
    await env.KV.put('cards', JSON.stringify(body));
    return corsResponse({ ok: true }, 200, origin);
  }

  /* --- Admins --- */
  if (path === '/admins' && method === 'GET') {
    const admins = await env.KV.get('admins', 'json') || [];
    return corsResponse(admins, 200, origin);
  }

  if (path === '/admins' && method === 'POST') {
    const body = await request.json();
    await env.KV.put('admins', JSON.stringify(body));
    return corsResponse({ ok: true }, 200, origin);
  }

  return corsResponse({ error: 'Rota não encontrada' }, 404, origin);
}

/* ── Helpers ──────────────────────────────────────────── */

function corsResponse(data, status = 200, origin = '') {
  const allowed = CORS_ORIGINS.includes(origin) ? origin : CORS_ORIGINS[0];
  return new Response(data === null ? null : JSON.stringify(data), {
    status,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': allowed,
      'Access-Control-Allow-Methods': 'GET, POST, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Access-Control-Allow-Credentials': 'true',
    },
  });
}

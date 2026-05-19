# CorretorTech — Guia do Projeto

Plataforma para corretores de saúde do Brasil (Anderson Souza / Jizelle Corretora).

---

## 🗂️ Estrutura de Repositórios e Deploys

| Pasta local | Repositório GitHub | URL em produção | Deploy |
|---|---|---|---|
| `bradesco-rede/` | `andersonaos88-ux/bradesco-rede` | `bradesco-rede.corretortech.com` | Cloudflare Pages (auto-deploy no push) |
| `bradesco-e3/` | `andersonaos88-ux/PortalE3` (root = `Claudinho/`) | `bradesco-e3.corretortech.com` | Cloudflare Pages (auto-deploy no push) |
| `portal-cotacao/` | `andersonaos88-ux/PortalE3` | `cotacao.corretortech.com` | Cloudflare Pages |
| `home/` | `andersonaos88-ux/PortalE3` | `corretortech.com` | Cloudflare Pages |
| `corretortech-auth/` | `andersonaos88-ux/PortalE3` | `api.corretortech.com` (Worker) | `wrangler deploy` |
| `saldo-cartao/` | `andersonaos88-ux/PortalE3` (aba Railway) | Railway (FastAPI + Playwright) | Push para GitHub → Railway auto-deploy |

> ⚠️ **REGRA CRÍTICA**: Edições locais NÃO chegam na produção automaticamente.
> Sempre fazer `git add <arquivo> && git commit && git push` no repo correto.
> Para bradesco-e3 e bradesco-rede: o git root é `/Users/andersonsouza/Desktop/Claudinho/`.

---

## 🔐 Autenticação

- **Cloudflare Access** protege todos os subdomínios via JWT cookie `CF_Authorization`
- Cookie é domain-specific — não cruza subdomínios diretamente
- **Solução adotada**: `home/index.html` salva nome do usuário no cookie `ct_nome` com `domain=.corretortech.com` após fetch do `/api/me`
- Os outros cards leem `ct_nome` para pré-preencher campo "Corretor/Consultor"

---

## 🃏 Cards de Apresentação

### Bradesco Rede (`bradesco-rede/index.html`)
- Gerador de proposta comercial Canal Rede
- Importa cotação via PDF (cop / sem cop identificados manualmente via UI após upload)
- **Rede Credenciada**: filtra hospitais e colunas pelos planos selecionados em `d.bradPlans`
- Plans → Tier: `Efetivo→Ef`, `Efetivo Plus→EP`, `Flex→Fx`, `Ideal→Id`, `Nacional→N`, `Nacional Plus→NP`
- `BRAD_REEMBOLSO_SUFFIX`: Nacional = [1x,2x,3x], Nacional Plus = [4x,6x,8x]
- IOF de 2.38% (`withIof()`) aplicado nos planos Bradesco, **NÃO** no Plano Atual

### Bradesco E3 (`bradesco-e3/index.html`)
- Idêntico ao Rede com adaptações visuais para o Canal E3
- Mesmas regras de IOF, PLAN_MAP, rede credenciada

### Portal Cotação (`portal-cotacao/index.html`)
- Usa cookie `ct_nome` para pré-preencher consultor

---

## 📦 PLAN_MAP (PDF → nome interno)

```js
'EFETIVO PLUS': 'Efetivo Plus', 'EFETIVO': 'Efetivo',
'NACIONAL PLUS': 'Nacional Plus', 'NACIONAL FLEX': 'Flex',
'NACIONAL III': 'Nacional', 'NACIONAL': 'Nacional',
'FLEX': 'Flex', 'IDEAL': 'Ideal', 'REGIONAL': 'Regional', 'SAUDE+': 'Saúde +'
// ⚠️ Ordem importa: strings mais longas primeiro (sort by length)
```

---

## 🚂 Saldo Cartão (Railway)

- **Stack**: FastAPI + Playwright (Chromium headless)
- **Portal**: `gestor.apoiocliente.com.br` (login com credenciais via env vars)
- **Keep-alive**: pinga `localhost:{PORT}/` a cada 5min para evitar sleep no Railway
- **Deploy**: push para GitHub → Railway auto-deploy (não usar `railway up` — falha com Playwright)
- **Env vars no Railway**: `PORTAL_EMAIL`, `PORTAL_SENHA`, `PORTAL_EMPRESA`

---

## 🛠️ Comandos Frequentes

```bash
# Deploy bradesco-rede
cd /Users/andersonsouza/Desktop/Claudinho/bradesco-rede
git add index.html && git commit -m "msg" && git push

# Deploy bradesco-e3 / portal-cotacao / home / corretortech-auth
cd /Users/andersonsouza/Desktop/Claudinho
git add bradesco-e3/index.html  # ou home/index.html etc.
git commit -m "msg" && git push

# Deploy Worker (corretortech-auth) — precisa de wrangler
cd /Users/andersonsouza/Desktop/Claudinho/corretortech-auth
wrangler deploy
```

---

## 🔧 Configurações Importantes

- **IOF**: `const IOF_RATE = 1.0238` — aplica em todos os planos Bradesco exceto Plano Atual
- **Cookie compartilhado**: `ct_nome`, domain=`.corretortech.com`, max-age=86400
- **Cloudflare KV**: usuários, planos, cartões
- **Cloudflare D1**: banco CRM

---

## 📋 Backlog / Pendências

- [ ] Canva templates (PNG) para capas das 3 apresentações — Anderson vai criar e enviar
- [ ] Agente monitoramento Rede Credenciada: acessa Painel do Corretor semanalmente, compara com D1, envia WhatsApp via Zaplus API (ainda precisa: URL/token Zaplus, número WhatsApp, credenciais do portal como env vars Railway)
- [ ] Remover `console.log` de debug da rede credenciada após confirmar que o filtro funciona

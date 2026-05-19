# API Saldo Cartão — Apoio ao Cliente

Bot que acessa o portal gestor.apoiocliente.com.br e retorna o saldo de um cartão pelos últimos 4 dígitos.

---

## Como funciona

```
POST /consultar-saldo
{ "ultimos_digitos": "3668" }

Resposta:
{ "cartao": "3668", "saldo": "R$ 4.301,75", "status": "sucesso", "portador": "ANDERSON OLIVEIRA DE SOUZA" }
```

---

## Rodar localmente

### 1. Instalar dependências
```bash
pip install -r requirements.txt
playwright install chromium
playwright install-deps chromium
```

### 2. Configurar variáveis de ambiente (opcional — já tem defaults)
```bash
export PORTAL_EMAIL="seu@email.com"
export PORTAL_SENHA="suasenha"
export PORTAL_EMPRESA="JIZELLE"
```

### 3. Iniciar a API
```bash
uvicorn main:app --reload --port 8000
```

### 4. Testar
```bash
curl -X POST http://localhost:8000/consultar-saldo \
  -H "Content-Type: application/json" \
  -d '{"ultimos_digitos": "3668"}'
```

---

## Deploy no Railway (gratuito / ~$5/mes)

1. Crie conta em https://railway.app
2. Clique em New Project -> Deploy from GitHub
3. Suba esta pasta no GitHub ou faça upload direto
4. Configure as variaveis de ambiente no painel Railway:
   - PORTAL_EMAIL
   - PORTAL_SENHA
   - PORTAL_EMPRESA
5. Railway detecta o Dockerfile automaticamente e faz o build
6. Sua URL sera algo como: https://saldo-cartao.up.railway.app

---

## Integração com sua ferramenta (Dynamics 365 / WhatsApp)

Quando o cliente mandar mensagem com os 4 digitos, sua ferramenta faz:

  POST https://sua-url.railway.app/consultar-saldo
  Content-Type: application/json
  Body: { "ultimos_digitos": "3668" }

Resposta JSON:
  {
    "cartao": "3668",
    "saldo": "R$ 4.301,75",
    "status": "sucesso",
    "portador": "ANDERSON OLIVEIRA DE SOUZA"
  }

Use o campo "saldo" para responder o cliente no WhatsApp.

---

## Fluxo do bot (etapas automatizadas)

1. Login com e-mail e senha
2. Seleciona empresa JIZELLE CORRETORA DE SEGUROS DE VIDA LTDA
3. Abre menu hamburguer
4. Clica em Portadores
5. Expande cada portador e clica em Ver todos os cartoes
6. Localiza o cartao pelos 4 ultimos digitos
7. Clica no cartao e depois no botao Extrato
8. Captura Saldo Atual no rodape do modal

---

## Seguranca

- Credenciais via variaveis de ambiente, nunca no codigo
- A API nao armazena dados de cartao
- Para producao: adicione um header de autenticacao simples no endpoint

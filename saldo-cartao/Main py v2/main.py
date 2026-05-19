from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from playwright.async_api import async_playwright
import asyncio
import os
import re

app = FastAPI(title="API Saldo Cartão - Apoio ao Cliente")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Credenciais via variáveis de ambiente (nunca hardcoded em produção)
EMAIL = os.getenv("PORTAL_EMAIL", "anderson@jizellecorretora.com.br")
SENHA = os.getenv("PORTAL_SENHA", "Anderson0102")
EMPRESA_FILTRO = os.getenv("PORTAL_EMPRESA", "JIZELLE")


class SaldoRequest(BaseModel):
    ultimos_digitos: str  # Ex: "3668"


class SaldoResponse(BaseModel):
    cartao: str
    saldo: str
    status: str
    portador: str | None = None


@app.get("/")
def health():
    return {"status": "ok", "servico": "API Saldo Cartão"}


@app.post("/consultar-saldo", response_model=SaldoResponse)
async def consultar_saldo(req: SaldoRequest):
    digitos = req.ultimos_digitos.strip()
    if len(digitos) != 4 or not digitos.isdigit():
        raise HTTPException(
            status_code=400,
            detail="Informe exatamente 4 dígitos numéricos."
        )
    try:
        resultado = await buscar_saldo(digitos)
        return resultado
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao consultar portal: {str(e)}"
        )


async def buscar_saldo(digitos: str) -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        try:
            # ── ETAPA 1: Login ──────────────────────────────────────────
            print("[1/8] Acessando portal...")
            await page.goto(
                "https://gestor.apoiocliente.com.br/#/gestor",
                wait_until="networkidle",
                timeout=30000
            )

            # Aguarda qualquer input de email/texto aparecer
            await page.wait_for_selector(
                'input[type="email"], input[placeholder*="mail"], input[placeholder*="E-mail"], input[placeholder*="Login"], input:first-of-type',
                timeout=15000
            )

            # Preenche email — tenta vários seletores
            for sel in ['input[type="email"]', 'input[placeholder*="mail"]', 'input[placeholder*="E-mail"]', 'input[placeholder*="Login"]']:
                try:
                    await page.fill(sel, EMAIL, timeout=3000)
                    break
                except Exception:
                    continue

            # Preenche senha
            for sel in ['input[type="password"]', 'input[placeholder*="enha"]', 'input[placeholder*="Senha"]']:
                try:
                    await page.fill(sel, SENHA, timeout=3000)
                    break
                except Exception:
                    continue

            # Clica em entrar
            for sel in ['button:has-text("ENTRAR")', 'button:has-text("Entrar")', 'button[type="submit"]', 'input[type="submit"]']:
                try:
                    await page.click(sel, timeout=3000)
                    break
                except Exception:
                    continue
            await page.wait_for_load_state("networkidle", timeout=15000)
            print("[1/8] Login OK")

            # ── ETAPA 2: Selecionar Empresa ─────────────────────────────
            print("[2/8] Selecionando empresa...")
            await page.wait_for_selector(
                'text=Selecione uma Empresa',
                timeout=10000
            )
            await page.click('text=Selecione uma Empresa')

            await page.wait_for_selector(
                'input[placeholder*="Filtrar"]',
                timeout=8000
            )
            await page.fill('input[placeholder*="Filtrar"]', EMPRESA_FILTRO)
            await asyncio.sleep(0.8)

            # Clica no item da lista que contém o filtro
            await page.locator(f'text={EMPRESA_FILTRO}').first.click()
            await page.wait_for_load_state("networkidle", timeout=15000)
            print("[2/8] Empresa selecionada OK")

            # ── ETAPA 3: Abrir menu hamburguer ──────────────────────────
            print("[3/8] Abrindo menu...")
            # Tenta vários seletores comuns para botão de menu
            menu_seletores = [
                'button.hamburger',
                '[class*="hamburger"]',
                '[class*="menu-btn"]',
                '[class*="navbar-toggler"]',
                'span.bar, span.burger',
                # fallback: primeiro botão da navbar
                'nav button',
                'header button',
            ]
            menu_aberto = False
            for sel in menu_seletores:
                try:
                    await page.click(sel, timeout=2000)
                    menu_aberto = True
                    break
                except Exception:
                    continue

            if not menu_aberto:
                # último recurso: clica nos 3 traços pelo ícone SVG
                await page.evaluate("""
                    () => {
                        const btns = document.querySelectorAll('button');
                        for(const b of btns) {
                            if(b.querySelector('svg') || b.innerText.trim() === '☰') {
                                b.click(); return;
                            }
                        }
                    }
                """)

            await asyncio.sleep(0.8)
            print("[3/8] Menu aberto OK")

            # ── ETAPA 4: Clicar em Portadores ───────────────────────────
            print("[4/8] Navegando para Portadores...")
            await page.wait_for_selector('text=Portadores', timeout=8000)
            await page.click('text=Portadores')
            await page.wait_for_load_state("networkidle", timeout=15000)
            await asyncio.sleep(1)
            print("[4/8] Portadores OK")

            # ── ETAPA 5+6: Buscar o cartão pelos últimos 4 dígitos ──────
            print(f"[5/8] Buscando cartão com final {digitos}...")
            portador_nome = None
            cartao_encontrado = False

            # Encontra todos os botões de expandir portador (seta ›)
            # e itera até encontrar o cartão com os dígitos
            max_tentativas = 3
            for tentativa in range(max_tentativas):
                # Pega todos os botões expand visíveis
                expand_btns = await page.locator(
                    'button[class*="expand"], button[class*="arrow"], '
                    'button[class*="chevron"], [class*="expand"] button, '
                    'td:last-child button, .portador button'
                ).all()

                if not expand_btns:
                    # fallback: pega todos os botões com "›" ou ">"
                    expand_btns = await page.locator('button').all()

                for btn in expand_btns:
                    try:
                        await btn.click(timeout=2000)
                        await asyncio.sleep(0.5)

                        # Verifica se apareceu "Ver todos os cartões"
                        ver_btn = page.locator('text=Ver todos os cartões')
                        if await ver_btn.count() > 0:
                            await ver_btn.first.click()
                            await asyncio.sleep(1)

                            # Verifica se o cartão com os dígitos está visível
                            cartao_locator = page.locator(f'text={digitos}')
                            if await cartao_locator.count() > 0:
                                # Captura nome do portador
                                try:
                                    portador_nome = await page.evaluate("""
                                        (digitos) => {
                                            const els = [...document.querySelectorAll('*')];
                                            for(const el of els) {
                                                if(el.innerText && el.innerText.includes('NOME:')) {
                                                    return el.innerText.match(/NOME:\\s*(.+)/)?.[1]?.trim() || null;
                                                }
                                            }
                                            return null;
                                        }
                                    """, digitos)
                                except Exception:
                                    pass

                                # Clica no cartão
                                await cartao_locator.first.click()
                                cartao_encontrado = True
                                break
                    except Exception:
                        continue

                if cartao_encontrado:
                    break
                await asyncio.sleep(0.5)

            if not cartao_encontrado:
                raise Exception(
                    f"Cartão com final {digitos} não encontrado. "
                    "Verifique se os dígitos estão corretos."
                )

            print(f"[5/8] Cartão {digitos} encontrado!")

            # ── ETAPA 7: Clicar em Extrato ──────────────────────────────
            print("[7/8] Abrindo extrato...")
            await page.wait_for_selector('text=Extrato', timeout=8000)
            # Garante que clica no botão Extrato (não no título)
            extrato_btn = page.locator('button:has-text("Extrato"), a:has-text("Extrato")').first
            if await extrato_btn.count() > 0:
                await extrato_btn.click()
            else:
                await page.click('text=Extrato')
            await asyncio.sleep(1.5)
            print("[7/8] Extrato aberto OK")

            # ── ETAPA 8: Capturar Saldo Atual ───────────────────────────
            print("[8/8] Capturando saldo...")
            await page.wait_for_selector('text=Saldo Atual', timeout=10000)

            saldo_texto = await page.evaluate("""
                () => {
                    const walker = document.createTreeWalker(
                        document.body,
                        NodeFilter.SHOW_TEXT
                    );
                    let node;
                    while(node = walker.nextNode()) {
                        if(node.textContent.includes('Saldo Atual')) {
                            return node.textContent.trim();
                        }
                    }
                    // fallback: pega innerText do elemento pai
                    const els = [...document.querySelectorAll('*')];
                    for(const el of els) {
                        if(el.children.length === 0 && el.innerText?.includes('Saldo Atual')) {
                            return el.innerText.trim();
                        }
                    }
                    return null;
                }
            """)

            if not saldo_texto:
                raise Exception("Texto 'Saldo Atual' não encontrado na página.")

            # Extrai o valor R$ X.XXX,XX
            match = re.search(r'R\$\s*[\d\.,]+', saldo_texto)
            saldo_valor = match.group(0).strip() if match else saldo_texto

            print(f"[8/8] Saldo capturado: {saldo_valor}")

            return {
                "cartao": digitos,
                "saldo": saldo_valor,
                "status": "sucesso",
                "portador": portador_nome,
            }

        finally:
            await browser.close()

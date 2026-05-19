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

EMAIL = os.getenv("PORTAL_EMAIL", "anderson@jizellecorretora.com.br")
SENHA = os.getenv("PORTAL_SENHA", "Anderson0102")


class SaldoRequest(BaseModel):
    ultimos_digitos: str


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
        raise HTTPException(status_code=400, detail="Informe exatamente 4 dígitos numéricos.")
    try:
        resultado = await buscar_saldo(digitos)
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar portal: {str(e)}")


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
            print("[1] Acessando portal...")
            await page.goto("https://gestor.apoiocliente.com.br/#/gestor", wait_until="networkidle", timeout=30000)
            await page.wait_for_selector("#gestor-usuario", timeout=15000)
            await page.fill("#gestor-usuario", EMAIL)
            await page.fill("#gestor-senha", SENHA)
            await page.click('button:has-text("ENTRAR")')
            await page.wait_for_load_state("networkidle", timeout=15000)
            print("[1] Login OK")

            # ── ETAPA 2: Selecionar Empresa JIZELLE ─────────────────────
            print("[2] Selecionando empresa...")
            await page.wait_for_selector(".btn-empresa", timeout=10000)
            await page.click(".btn-empresa")
            await asyncio.sleep(1)
            # Campo de filtro tem id="input-usuario"
            await page.wait_for_selector("#input-usuario", timeout=8000)
            await page.fill("#input-usuario", "JIZELLE")
            await asyncio.sleep(0.8)
            # Clica na linha da tabela que contém JIZELLE
            await page.locator("td:has-text('JIZELLE CORRETORA DE SEGUROS DE VIDA LTDA')").first.click()
            await page.wait_for_load_state("networkidle", timeout=15000)
            print("[2] Empresa OK")

            # ── ETAPA 3: Fechar popup de aviso se aparecer ──────────────
            await asyncio.sleep(1)
            try:
                close_btn = page.locator(".ui-dialog-titlebar-close, .ui-overlaypanel-close, .p-dialog-header-close").first
                if await close_btn.count() > 0:
                    await close_btn.click(timeout=2000)
            except Exception:
                pass
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass
            await asyncio.sleep(0.5)

            # ── ETAPA 4: Abrir menu e ir para Portadores ────────────────
            print("[3] Abrindo menu...")
            await page.wait_for_selector("#btn-menu", timeout=8000)
            await page.click("#btn-menu")
            await asyncio.sleep(0.8)
            # Clica no item Portadores pelo seletor real
            await page.locator(".menu-item-gestor:has-text('Portadores')").first.click()
            await page.wait_for_load_state("networkidle", timeout=15000)
            await asyncio.sleep(1)
            print("[3] Portadores OK")

            # ── ETAPA 5: Buscar cartão pelos últimos 4 dígitos ──────────
            print(f"[4] Buscando cartão {digitos}...")
            portador_nome = None
            cartao_encontrado = False

            # Pega todas as linhas de portadores (panel-header)
            linhas = await page.locator(".p-grid.panel-header").all()

            for linha in linhas:
                # Clica para expandir
                try:
                    await linha.click(timeout=2000)
                    await asyncio.sleep(1)
                except Exception:
                    continue

                # Verifica se apareceu "Ver todos os cartões"
                ver_btn = page.locator('button:has-text("Ver todos os cartões")')
                if await ver_btn.count() > 0:
                    await ver_btn.first.click()
                    await asyncio.sleep(1)

                # Verifica se o cartão com os dígitos está visível
                card_locator = page.locator(f"div.portador-card:has-text('{digitos}')")
                if await card_locator.count() > 0:
                    # Captura nome do portador desta linha
                    try:
                        portador_nome = await linha.locator("td, span").nth(1).inner_text()
                        portador_nome = portador_nome.strip()
                    except Exception:
                        pass
                    await card_locator.first.click()
                    cartao_encontrado = True
                    break

            if not cartao_encontrado:
                raise Exception(f"Cartão com final {digitos} não encontrado.")

            print(f"[4] Cartão {digitos} encontrado!")

            # ── ETAPA 6: Clicar em Extrato no accordion ─────────────────
            print("[5] Abrindo extrato...")
            await asyncio.sleep(1)
            extrato_header = page.locator(".ui-accordion-header:has-text('Extrato')")
            await extrato_header.wait_for(timeout=8000)
            await extrato_header.click()
            await asyncio.sleep(1.5)
            print("[5] Extrato aberto OK")

            # ── ETAPA 7: Capturar Saldo Atual ───────────────────────────
            print("[6] Capturando saldo...")
            await page.wait_for_selector("td:has-text('Saldo Atual')", timeout=10000)

            saldo_texto = await page.evaluate("""
                () => {
                    const tds = document.querySelectorAll('td');
                    for(const td of tds) {
                        if(td.innerText && td.innerText.includes('Saldo Atual')) {
                            return td.innerText.trim();
                        }
                    }
                    return null;
                }
            """)

            if not saldo_texto:
                raise Exception("Saldo Atual não encontrado.")

            match = re.search(r'R\$\s*[\d\.,]+', saldo_texto)
            saldo_valor = match.group(0).strip() if match else saldo_texto

            print(f"[6] Saldo: {saldo_valor}")

            return {
                "cartao": digitos,
                "saldo": saldo_valor,
                "status": "sucesso",
                "portador": portador_nome,
            }

        finally:
            await browser.close()

import asyncio
import logging
import os
from pathlib import Path

import requests
from playwright.async_api import async_playwright

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def carregar_variaveis_ambiente(arquivo='.env'):
    caminho = Path(arquivo)
    if not caminho.exists():
        return

    for linha in caminho.read_text(encoding='utf-8').splitlines():
        linha = linha.strip()
        if not linha or linha.startswith('#') or '=' not in linha:
            continue

        chave, valor = linha.split('=', 1)
        chave = chave.strip()
        valor = valor.strip().strip("'\"")
        os.environ.setdefault(chave, valor)


carregar_variaveis_ambiente()

# --- CONFIGURAÇÕES ---
URL_AGENDAMENTO = os.getenv('URL_AGENDAMENTO', 'COLOQUE_A_URL_AQUI')
ESPECIALIDADE = 'CLÍNICA MÉDICA'
TEMPO_ESPERA_MINUTOS = 5

# --- CREDENCIAIS DO TELEGRAM ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
CHAT_ID = os.getenv('CHAT_ID', '')

if not TELEGRAM_TOKEN or not CHAT_ID:
    raise RuntimeError('Defina TELEGRAM_TOKEN e CHAT_ID no arquivo .env')

def enviar_mensagem_telegram(texto):
    """Envia uma mensagem de texto simples para o Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': CHAT_ID, 'text': texto})
    except Exception as e:
        logging.error(f"Erro ao enviar log para o Telegram: {e}")

def enviar_foto_telegram(caminho_imagem, legenda):
    """Envia a captura de tela para o Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    try:
        with open(caminho_imagem, 'rb') as photo:
            dados = {'chat_id': CHAT_ID, 'caption': legenda}
            arquivos = {'photo': photo}
            requests.post(url, data=dados, files=arquivos)
    except Exception as e:
        logging.error(f"Erro ao enviar foto para o Telegram: {e}")

async def monitorar_vagas():
    async with async_playwright() as p:
        logging.info("Tentando conectar ao navegador na porta 9222...")
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            
            # Avisa no Telegram que o robô foi ligado
            enviar_mensagem_telegram("🤖 Robô de agendamento iniciado! Iniciando monitoramento...")
            
            while True:
                logging.info(f"=== Iniciando nova verificação para {ESPECIALIDADE} ===")
                
                page = None
                for aba in context.pages:
                    if "hspm" in aba.url.lower() or "agendamento" in aba.url.lower():
                        page = aba
                        break
                
                if page is None:
                    page = context.pages[0]
                    
                await page.bring_to_front()
                
                try:
                    await page.wait_for_load_state('networkidle', timeout=5000)
                except Exception:
                    pass 
                
                # PASSO 1, 2 e 3: Navegação e Pesquisa
                logging.info("Realizando navegação e pesquisa...")
                await page.locator("label.rz-dropdown-label").first.click(timeout=10000)
                await page.wait_for_timeout(1000) 
                
                await page.get_by_text(ESPECIALIDADE).first.click(timeout=10000)
                await page.locator("button:has-text('Pesquisar')").first.click(timeout=10000)
                
                # PASSO 4: Verificar o resultado
                logging.info("Aguardando a resposta do sistema...")
                botao_ok = page.locator("button:has-text('OK')").first
                
                try:
                    # Espera 5 segundos pelo modal de erro
                    await botao_ok.wait_for(state='visible', timeout=5000)
                    logging.info("Aviso de 'Não há vagas' detectado.")
                    
                    # LOG DE ROTINA NO TELEGRAM
                    enviar_mensagem_telegram(f"🔄 Busca realizada. Nenhuma vaga para {ESPECIALIDADE} no momento.")
                    
                    logging.info("Fechando a janela de aviso e zerando menu...")
                    await botao_ok.click()
                    await page.wait_for_timeout(1000)
                    
                except Exception:
                    # CENÁRIO COM VAGA
                    logging.info("🚨 NENHUM AVISO DE ERRO DETECTADO! POSSÍVEL VAGA ENCONTRADA!")
                    
                    caminho_print = 'vaga_disponivel.png'
                    try:
                        await page.screenshot(path=caminho_print, timeout=10000)
                        
                        # LOG DE ALERTA COM FOTO NO TELEGRAM
                        enviar_foto_telegram(caminho_print, f"🚨 ATENÇÃO! Possível vaga para {ESPECIALIDADE}! Acesse o site agora!")
                        
                    except Exception as e:
                        logging.warning(f"Não foi possível tirar o print da tela: {e}")
                        # Manda mensagem mesmo se o print falhar
                        enviar_mensagem_telegram(f"🚨 ATENÇÃO! Possível vaga para {ESPECIALIDADE}, mas o print falhou! Acesse o site!")
                
                # RESET
                try:
                    await page.locator("button:has-text('Limpar')").first.click(timeout=5000)
                    await page.wait_for_timeout(1000)
                except Exception:
                    await page.reload()
                    await page.wait_for_load_state('networkidle')
                
                # LOOP
                logging.info(f"Ciclo concluído. Dormindo por {TEMPO_ESPERA_MINUTOS} minutos...")
                await asyncio.sleep(TEMPO_ESPERA_MINUTOS * 60)
                    
        except Exception as e:
            msg_erro = f"❌ Erro crítico no robô: {e}"
            logging.error(msg_erro)
            enviar_mensagem_telegram(msg_erro)
            
        finally:
            if 'browser' in locals():
                logging.info("Desconectando do navegador...")
                await browser.close()

if __name__ == "__main__":
    asyncio.run(monitorar_vagas())
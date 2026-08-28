import asyncio
import logging
import os
import requests
from playwright.async_api import async_playwright

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- CONFIGURAÇÕES ---
URL_AGENDAMENTO = os.environ.get('URL_AGENDAMENTO')

# Agora temos uma LISTA de especialidades
ESPECIALIDADES = [
    'CLÍNICA MÉDICA',
    'CLÍNICA MÉDICA - HÍBRIDA',
    'DERMATOLOGIA',
    'GASTROCLÍNICA', 
    'NUTRIÇÃO - DIETÉTICA',
    'ODONTOLOGIA - DENTÍSTICA',
    'OTORRINOLARINGOLOGIA',
    'UROLOGIA'
]

TEMPO_ESPERA_MINUTOS = 5

# --- CREDENCIAIS DO TELEGRAM ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

if not TELEGRAM_TOKEN or not CHAT_ID or not URL_AGENDAMENTO:
    raise ValueError("❌ ERRO: TELEGRAM_TOKEN, CHAT_ID ou URL_AGENDAMENTO não encontrados no arquivo .env!")

def enviar_mensagem_telegram(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': CHAT_ID, 'text': texto})
    except Exception as e:
        logging.error(f"Erro ao enviar log para o Telegram: {e}")

def enviar_foto_telegram(caminho_imagem, legenda):
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
            
            enviar_mensagem_telegram("🤖 Robô iniciado! Buscando em múltiplas especialidades...")
            
            while True:
                logging.info(f"=== Iniciando varredura nas {len(ESPECIALIDADES)} especialidades ===")
                
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
                
                # LAÇO PARA VERIFICAR CADA ESPECIALIDADE DA LISTA
                for especialidade in ESPECIALIDADES:
                    logging.info(f"🔎 Verificando: {especialidade}...")
                    
                    try:
                        # 1. Abre a caixa e seleciona
                        await page.locator("label.rz-dropdown-label").first.click(timeout=10000)
                        await page.wait_for_timeout(1000) 
                        
                        # exact=True garante que ele não confunda nomes parecidos
                        await page.get_by_text(especialidade, exact=True).first.click(timeout=10000)
                        
                        # 2. Pesquisa
                        await page.locator("button:has-text('Pesquisar')").first.click(timeout=10000)
                        
                        # 3. Lê o resultado
                        botao_ok = page.locator("button:has-text('OK')").first
                        
                        try:
                            await botao_ok.wait_for(state='visible', timeout=5000)
                            logging.info(f"❌ Sem vagas para {especialidade}.")
                            
                            # Fecha o aviso
                            await botao_ok.click()
                            await page.wait_for_timeout(1000)
                            
                        except Exception:
                            logging.info(f"🚨 VAGA ENCONTRADA PARA {especialidade}!")
                            
                            # O nome do arquivo da foto agora inclui o nome da especialidade
                            nome_arquivo = f'vaga_{especialidade.replace(" ", "_")}.png'
                            try:
                                await page.screenshot(path=nome_arquivo, timeout=10000)
                                enviar_foto_telegram(nome_arquivo, f"🚨 VAGA LIBERADA: {especialidade}! Corra para o site!")
                            except Exception as e:
                                logging.warning(f"Falha ao printar: {e}")
                                enviar_mensagem_telegram(f"🚨 VAGA LIBERADA: {especialidade}! O print falhou, mas corra para o site!")
                    
                    except Exception as e_busca:
                        logging.error(f"Erro ao processar a especialidade {especialidade}: {e_busca}")

                    # 4. RESET: Clica em Limpar antes de ir para a próxima especialidade do loop
                    try:
                        await page.locator("button:has-text('Limpar')").first.click(timeout=5000)
                        await page.wait_for_timeout(1500)
                    except Exception:
                        await page.reload()
                        await page.wait_for_load_state('networkidle')
                
                # Após passar por todas as opções, o robô dorme
                logging.info(f"Varredura concluída. Dormindo por {TEMPO_ESPERA_MINUTOS} minutos...")
                await asyncio.sleep(TEMPO_ESPERA_MINUTOS * 60)
                    
        except Exception as e:
            msg_erro = f"❌ Erro crítico no robô: {e}"
            logging.error(msg_erro)
            enviar_mensagem_telegram(msg_erro)
            
        finally:
            if 'browser' in locals():
                logging.info("Desconectando...")
                await browser.close()

if __name__ == "__main__":
    asyncio.run(monitorar_vagas())
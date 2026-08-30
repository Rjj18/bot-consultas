import asyncio
import logging
import os
import requests
from datetime import datetime
from playwright.async_api import async_playwright

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- CONFIGURAÇÕES ---
URL_AGENDAMENTO = os.environ.get('URL_AGENDAMENTO')
CPF = os.environ.get('CPF')
SENHA = os.environ.get('SENHA')

ESPECIALIDADES = [
    'CLÍNICA MÉDICA',
    'DERMATOLOGIA',
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
    raise ValueError("❌ ERRO: Faltam variáveis de ambiente no arquivo .env!")

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

def limpar_mensagens_pendentes():
    """Lê o histórico do bot para ignorar mensagens antigas antes de pedir o CAPTCHA."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    try:
        res = requests.get(url).json()
        if res.get('ok') and res.get('result'):
            return res['result'][-1]['update_id'] + 1
    except Exception:
        pass
    return None

async def aguardar_captcha_telegram(offset):
    """Fica escutando o Telegram até você enviar uma mensagem de texto."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    logging.info("Aguardando você digitar o CAPTCHA no Telegram...")
    
    while True:
        try:
            # Consulta o Telegram sem travar o processamento do robô
            res = await asyncio.to_thread(
                requests.get, 
                url, 
                params={'offset': offset, 'timeout': 5}, 
                timeout=10
            )
            dados = res.json()
            if dados.get('ok') and dados.get('result'):
                for update in dados['result']:
                    novo_offset = update['update_id'] + 1
                    mensagem = update.get('message', {}).get('text', '').strip()
                    
                    if mensagem:
                        return mensagem, novo_offset
                    else:
                        offset = novo_offset
        except Exception:
            pass # Ignora erros de rede temporários
        
        await asyncio.sleep(2)

async def monitorar_vagas():
    async with async_playwright() as p:
        logging.info("Tentando conectar ao navegador na porta 9222...")
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            
            enviar_mensagem_telegram("🤖 Robô iniciado! Modo interativo via Telegram ativado. Monitorando vagas...")
            
            # Marca o momento em que a sessão começou
            hora_inicio_sessao = datetime.now()
            
            while True:
                page = None
                for aba in context.pages:
                    if "hspm" in aba.url.lower() or "agendamento" in aba.url.lower():
                        page = aba
                        break
                
                if page is None:
                    page = context.pages[0]
                    
                await page.bring_to_front()
                
                # Aguarda estabilizar
                try:
                    await page.wait_for_load_state('networkidle', timeout=5000)
                except Exception:
                    pass 
                
                # --- 1. VERIFICAÇÃO DE SESSÃO EXPIRADA E RECUPERAÇÃO VIA TELEGRAM ---
                tela_login = page.locator("button:has-text('ENTRAR')").first
                
                if await tela_login.is_visible():
                    logging.warning("Sessão expirada detectada. Iniciando fluxo de recuperação pelo Telegram...")
                    
                    # Tira print da tela de login para capturar o CAPTCHA
                    caminho_print = 'print_login.png'
                    await page.screenshot(path=caminho_print)
                    
                    # Limpa mensagens velhas para não pegar lixo
                    offset = limpar_mensagens_pendentes()
                    
                    # Envia a foto pedindo ajuda
                    enviar_foto_telegram(caminho_print, "🚨 A sessão caiu! Digite APENAS o texto da imagem aqui no chat para eu fazer o login:")
                    
                    # Fica aguardando a sua resposta no Telegram
                    codigo_captcha, _ = await aguardar_captcha_telegram(offset)
                    
                    logging.info(f"CAPTCHA recebido do Telegram: {codigo_captcha}")
                    enviar_mensagem_telegram(f"🤖 Entendido! Injetando '{codigo_captcha}' e tentando logar...")
                    
                    # Preenche CPF e Senha se estiverem no .env
                    if CPF and SENHA:
                        logging.info("Credenciais identificadas. Preenchendo CPF e Senha...")
                        
                        # Foca nos campos nativos do Radzen pela ordem que aparecem na tela
                        campo_cpf = page.locator("input.rz-textbox").nth(0)
                        campo_senha = page.locator("input.rz-textbox").nth(1)
                        
                        # Limpa o campo de CPF (caso tenha sujeira) e digita tecla por tecla para a máscara funcionar
                        await campo_cpf.click()
                        await campo_cpf.clear()
                        await campo_cpf.press_sequentially(CPF, delay=100)
                        
                        # Preenche a senha
                        await campo_senha.click()
                        await campo_senha.clear()
                        await campo_senha.fill(SENHA)
                    else:
                        msg_alerta = "⚠️ CPF ou SENHA não encontrados no arquivo .env! Tentando logar só com o CAPTCHA..."
                        logging.warning(msg_alerta)
                        enviar_mensagem_telegram(msg_alerta)
                    
                    # Injeta o CAPTCHA usando o placeholder do site
                    campo_captcha = page.get_by_placeholder("Digite o Texto da Imagem", exact=False).first
                    await campo_captcha.fill(codigo_captcha)
                    
                    # Clica no botão para logar
                    await tela_login.click()
                    
                    # Aguarda uns segundos para ver a resposta do site
                    await page.wait_for_timeout(5000)
                    
                   # Verifica se o botão "ENTRAR" ainda está visível (ex: CAPTCHA estava errado)
                    if not await tela_login.is_visible():
                        enviar_mensagem_telegram("✅ Login realizado com sucesso! Indo para a tela de agendamento...")
                        logging.info("Forçando navegação para a URL de agendamento...")
                        
                        # Força o navegador a ir para a página correta após o login
                        await page.goto(URL_AGENDAMENTO)
                        await page.wait_for_load_state('networkidle')
                        
                        hora_inicio_sessao = datetime.now() # Reseta o contador
                    else:
                        enviar_mensagem_telegram("❌ Falha no login (possível CAPTCHA incorreto ou falha no sistema). Solicitando nova tentativa...")
                    # Recomeça o loop. Se falhou, ele vai tirar outro print e pedir de novo. Se passou, vai buscar vagas.
                    continue 
                
                # --- 2. CÁLCULO DE TEMPO LOGADO ---
                tempo_online = datetime.now() - hora_inicio_sessao
                horas, resto = divmod(tempo_online.seconds, 3600)
                minutos, _ = divmod(resto, 60)
                
                logging.info("="*50)
                logging.info(f"⏱️ Tempo de sessão contínua: {horas}h e {minutos}m")
                logging.info(f"🔎 Iniciando varredura nas {len(ESPECIALIDADES)} especialidades...")
                logging.info("="*50)

                # --- 3. BUSCA DAS ESPECIALIDADES ---
                for especialidade in ESPECIALIDADES:
                    logging.info(f"Processando: {especialidade}...")
                    
                    try:
                        await page.locator("label.rz-dropdown-label").first.click(timeout=10000)
                        await page.wait_for_timeout(1000) 
                        
                        await page.get_by_text(especialidade, exact=True).first.click(timeout=10000)
                        await page.locator("button:has-text('Pesquisar')").first.click(timeout=10000)
                        
                        botao_ok = page.locator("button:has-text('OK')").first
                        
                        try:
                            await botao_ok.wait_for(state='visible', timeout=5000)
                            await botao_ok.click()
                            await page.wait_for_timeout(1000)
                            
                        except Exception:
                            logging.info(f"🚨 VAGA ENCONTRADA PARA {especialidade}!")
                            nome_arquivo = f'vaga_{especialidade.replace(" ", "_")}.png'
                            
                            try:
                                await page.screenshot(path=nome_arquivo, timeout=10000)
                                enviar_foto_telegram(nome_arquivo, f"🚨 VAGA LIBERADA: {especialidade}! Corra para o site!")
                            except Exception as e:
                                logging.warning(f"Falha ao printar: {e}")
                                enviar_mensagem_telegram(f"🚨 VAGA LIBERADA: {especialidade}! O print falhou, acesse o site!")
                    
                    except Exception as e_busca:
                        logging.error(f"Erro na especialidade {especialidade}: {e_busca}")

                    try:
                        await page.locator("button:has-text('Limpar')").first.click(timeout=5000)
                        await page.wait_for_timeout(1500)
                    except Exception:
                        await page.reload()
                        await page.wait_for_load_state('networkidle')
                
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
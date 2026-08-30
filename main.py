import asyncio
import logging
import os
import requests
import csv
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

TEMPO_ESPERA_MINUTOS = 5

# --- CREDENCIAIS DO TELEGRAM ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

if not TELEGRAM_TOKEN or not CHAT_ID or not URL_AGENDAMENTO:
    raise ValueError("❌ ERRO: Faltam variáveis de ambiente (TELEGRAM_TOKEN, CHAT_ID ou URL_AGENDAMENTO) no arquivo .env!")

def carregar_especialidades():
    """Lê o arquivo txt e retorna uma lista atualizada de especialidades."""
    arquivo = 'especialidades.txt'
    if not os.path.exists(arquivo):
        logging.error(f"❌ Arquivo '{arquivo}' não encontrado! Crie o arquivo com uma especialidade por linha.")
        return []
    
    with open(arquivo, 'r', encoding='utf-8') as f:
        # Lê as linhas, remove espaços em branco/quebras de linha e ignora as linhas que estiverem vazias
        return [linha.strip() for linha in f if linha.strip()]

def enviar_mensagem_telegram(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': CHAT_ID, 'text': texto})
    except Exception as e:
        logging.error(f"Erro ao enviar log para o Telegram: {e}")

def enviar_foto_telegram(caminho_imagem, legenda):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    try:
        if os.path.exists(caminho_imagem):
            with open(caminho_imagem, 'rb') as photo:
                dados = {'chat_id': CHAT_ID, 'caption': legenda}
                arquivos = {'photo': photo}
                requests.post(url, data=dados, files=arquivos)
        else:
            enviar_mensagem_telegram(f"{legenda} (Print indisponível)")
    except Exception as e:
        logging.error(f"Erro ao enviar foto para o Telegram: {e}")

def limpar_mensagens_pendentes():
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    try:
        res = requests.get(url).json()
        if res.get('ok') and res.get('result'):
            return res['result'][-1]['update_id'] + 1
    except Exception:
        pass
    return None

def registrar_dados_csv(especialidade, status):
    arquivo_csv = 'historico_buscas.csv'
    arquivo_existe = os.path.isfile(arquivo_csv)
    
    try:
        with open(arquivo_csv, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not arquivo_existe:
                writer.writerow(['data_hora', 'especialidade', 'status'])
            
            agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            writer.writerow([agora, especialidade, status])
    except Exception as e:
        logging.error(f"Erro ao salvar dados no CSV: {e}")

async def aguardar_captcha_telegram(offset):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    logging.info("Aguardando você digitar o CAPTCHA no Telegram...")
    
    while True:
        try:
            res = await asyncio.to_thread(requests.get, url, params={'offset': offset, 'timeout': 5}, timeout=10)
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
            pass 
        await asyncio.sleep(2)

async def monitorar_vagas():
    async with async_playwright() as p:
        logging.info("Tentando conectar ao navegador na porta 9222...")
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            
            enviar_mensagem_telegram("🤖 Robô iniciado! Monitorando vagas com leitura dinâmica de especialidades...")
            hora_inicio_sessao = datetime.now()
            
            while True:
                try: 
                    # CARREGA AS ESPECIALIDADES NO INÍCIO DE CADA CICLO
                    especialidades_ativas = carregar_especialidades()
                    if not especialidades_ativas:
                        logging.warning("⚠️ Lista de especialidades vazia. Verifique o arquivo 'especialidades.txt'. Aguardando 1 minuto...")
                        await asyncio.sleep(60)
                        continue
                    
                    page = None
                    for aba in context.pages:
                        if "hspm" in aba.url.lower() or "agendamento" in aba.url.lower():
                            page = aba
                            break
                    
                    if page is None:
                        page = context.pages[0]
                        
                    await page.bring_to_front()
                    
                    if "hspm" not in page.url.lower():
                        logging.info("Página inicial não é o HSPM. Navegando para o portal...")
                        await page.goto(URL_AGENDAMENTO)
                    
                    try:
                        await page.wait_for_load_state('networkidle', timeout=5000)
                    except Exception:
                        pass 
                    
                    tela_login = page.locator("button:has-text('ENTRAR')").first
                    
                    try:
                        await tela_login.wait_for(state='visible', timeout=5000)
                    except:
                        pass
                    
                    # --- 1. VERIFICAÇÃO DE SESSÃO EXPIRADA E RECUPERAÇÃO VIA TELEGRAM ---
                    if await tela_login.is_visible():
                        logging.warning("Sessão expirada detectada. Iniciando fluxo de recuperação pelo Telegram...")
                        
                        caminho_print = 'print_login.png'
                        
                        if os.path.exists(caminho_print):
                            os.remove(caminho_print)
                            
                        try:
                            await page.evaluate("window.stop()")
                            await page.bring_to_front()
                            await page.wait_for_timeout(1000) 
                            await page.screenshot(path=caminho_print, timeout=10000)
                        except Exception as e:
                            logging.warning(f"O print da tela cheia falhou. Erro: {e}")
                            try:
                                await page.locator("body").screenshot(path=caminho_print, timeout=5000)
                            except Exception as e2:
                                logging.error("Print completamente indisponível.")
                        
                        offset = limpar_mensagens_pendentes()
                        enviar_foto_telegram(caminho_print, "🚨 A sessão caiu! Digite APENAS o texto da imagem aqui no chat para eu fazer o login:")
                        
                        codigo_captcha, _ = await aguardar_captcha_telegram(offset)
                        
                        logging.info(f"CAPTCHA recebido do Telegram: {codigo_captcha}")
                        enviar_mensagem_telegram(f"🤖 Entendido! Injetando '{codigo_captcha}' e tentando logar...")
                        
                        if CPF and SENHA:
                            logging.info("Credenciais identificadas. Preenchendo CPF e Senha...")
                            campo_cpf = page.locator("input.rz-textbox").nth(0)
                            campo_senha = page.locator("input.rz-textbox").nth(1)
                            
                            await campo_cpf.click()
                            await campo_cpf.clear()
                            await campo_cpf.press_sequentially(CPF, delay=100)
                            
                            await campo_senha.click()
                            await campo_senha.clear()
                            await campo_senha.fill(SENHA)
                        
                        campo_captcha = page.get_by_placeholder("Digite o Texto da Imagem", exact=False).first
                        await campo_captcha.fill(codigo_captcha)
                        await tela_login.click()
                        await page.wait_for_timeout(5000)
                        
                        if not await tela_login.is_visible():
                            enviar_mensagem_telegram("✅ Login realizado com sucesso! Indo para a tela de agendamento...")
                            logging.info("Forçando navegação para a URL de agendamento...")
                            await page.goto(URL_AGENDAMENTO)
                            await page.wait_for_load_state('networkidle')
                            hora_inicio_sessao = datetime.now() 
                        else:
                            enviar_mensagem_telegram("❌ Falha no login (possível CAPTCHA incorreto ou site lento). Solicitando nova tentativa...")
                        continue 
                    
                    # --- 2. CÁLCULO DE TEMPO LOGADO ---
                    tempo_online = datetime.now() - hora_inicio_sessao
                    horas, resto = divmod(tempo_online.seconds, 3600)
                    minutos, _ = divmod(resto, 60)
                    
                    logging.info("="*50)
                    logging.info(f"⏱️ Tempo de sessão contínua: {horas}h e {minutos}m")
                    logging.info(f"🔎 Iniciando varredura rápida nas {len(especialidades_ativas)} especialidades...")
                    logging.info("="*50)

                    # --- 3. BUSCA DAS ESPECIALIDADES E COLETA DE DADOS ---
                    for especialidade in especialidades_ativas:
                        if await tela_login.is_visible():
                            logging.warning(f"🚨 Fui deslogado enquanto procurava {especialidade}! Pausando o ciclo...")
                            break
                        
                        logging.info(f"Processando: {especialidade}...")
                        
                        try:
                            await page.bring_to_front()
                            
                            await page.locator("label.rz-dropdown-label").first.click(timeout=5000)
                            await page.wait_for_timeout(500)
                            
                            await page.get_by_text(especialidade, exact=True).first.click(timeout=5000)
                            await page.locator("button:has-text('Pesquisar')").first.click(timeout=5000)
                            
                            botao_ok = page.locator("button:has-text('OK')").first
                            
                            try:
                                await botao_ok.wait_for(state='visible', timeout=5000)
                                await botao_ok.click()
                                await page.wait_for_timeout(500)
                                
                                registrar_dados_csv(especialidade, 'SEM_VAGA')
                                logging.info(f"❌ Sem vagas para {especialidade}.")
                                
                            except Exception:
                                logging.info(f"🚨 VAGA ENCONTRADA PARA {especialidade}!")
                                nome_arquivo = f'vaga_{especialidade.replace(" ", "_")}.png'
                                registrar_dados_csv(especialidade, 'VAGA_ENCONTRADA')
                                
                                try:
                                    await page.bring_to_front()
                                    await page.wait_for_timeout(1000) 
                                    await page.screenshot(path=nome_arquivo, timeout=10000)
                                    enviar_foto_telegram(nome_arquivo, f"🚨 VAGA LIBERADA: {especialidade}! Corra para o site!")
                                except Exception as e:
                                    logging.warning(f"O print da vaga falhou por lentidão, ignorando erro: {e}")
                                    enviar_mensagem_telegram(f"🚨 VAGA LIBERADA: {especialidade}! O print falhou, mas corra para o site!")
                        
                        except Exception as e_busca:
                            logging.error(f"Erro na especialidade {especialidade}: {e_busca}")

                        try:
                            await page.locator("button:has-text('Limpar')").first.click(timeout=5000)
                            await page.wait_for_timeout(1000)
                        except Exception:
                            await page.reload()
                            await page.wait_for_load_state('networkidle')
                    
                    logging.info(f"Varredura concluída. Dormindo por {TEMPO_ESPERA_MINUTOS} minutos...")
                    await asyncio.sleep(TEMPO_ESPERA_MINUTOS * 60)
                
                except Exception as loop_error:
                    msg_falha = f"⚠️ O robô engasgou, mas não vai desligar! Erro: {loop_error}. Recomeçando em 1 minuto..."
                    logging.error(msg_falha)
                    await asyncio.sleep(60)
                    
        except Exception as e:
            msg_erro = f"❌ Erro crítico de conexão com o navegador: {e}"
            logging.error(msg_erro)
            enviar_mensagem_telegram(msg_erro)
            
        finally:
            if 'browser' in locals():
                logging.info("Desconectando...")
                await browser.close()

if __name__ == "__main__":
    asyncio.run(monitorar_vagas())
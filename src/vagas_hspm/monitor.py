"""Orquestração do loop de monitoramento: conecta as peças e mantém o robô rodando."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

from .browser import PortalAgendamento
from .config import Settings
from .models import StatusBusca
from .storage import HistoricoBuscas, carregar_especialidades
from .telegram_client import TelegramClient

logger = logging.getLogger(__name__)


async def _recuperar_sessao(
    portal: PortalAgendamento, telegram: TelegramClient, settings: Settings
) -> bool:
    """Fluxo de recuperação de sessão expirada via Telegram. Retorna True se logou."""
    logger.warning("Sessão expirada detectada. Iniciando recuperação via Telegram...")
    caminho_print = Path("print_login.png")

    tem_print = await portal.capturar_print(caminho_print)
    offset = await telegram.limpar_updates_pendentes()

    if tem_print:
        await telegram.enviar_foto(
            caminho_print, "🚨 A sessão caiu! Digite o texto da imagem para eu logar:"
        )
    else:
        await telegram.enviar_mensagem(
            "🚨 A sessão caiu! (print indisponível) Digite o texto do CAPTCHA:"
        )

    captcha = await telegram.aguardar_resposta(offset)
    logger.info("CAPTCHA recebido do Telegram.")
    await telegram.enviar_mensagem(f"🤖 Entendido! Tentando logar com '{captcha}'...")

    await portal.fazer_login(settings.cpf, settings.senha, captcha)

    if await portal.esta_deslogado():
        await telegram.enviar_mensagem(
            "❌ Falha no login (CAPTCHA incorreto ou site lento). Vou tentar de novo."
        )
        return False

    await telegram.enviar_mensagem("✅ Login realizado! Indo para a tela de agendamento...")
    await portal.ir_para_agendamento()
    return True


async def _ciclo_de_busca(
    portal: PortalAgendamento,
    telegram: TelegramClient,
    historico: HistoricoBuscas,
    especialidades: list[str],
) -> None:
    for especialidade in especialidades:
        if await portal.deslogou_agora():
            logger.warning("Deslogado durante a busca por %s. Encerrando o ciclo.", especialidade)
            return

        logger.info("Processando: %s", especialidade)
        try:
            status = await portal.buscar_especialidade(especialidade)
        except Exception as e:
            logger.error("Erro ao buscar especialidade %s: %s", especialidade, e)
            await portal.limpar_filtro()
            continue

        historico.registrar(especialidade, status)

        if status is StatusBusca.SEM_VAGA:
            logger.info("Sem vagas para %s.", especialidade)
        else:
            logger.info("VAGA ENCONTRADA PARA %s!", especialidade)
            caminho = Path(f"vaga_{especialidade.replace(' ', '_')}.png")
            tem_print = await portal.capturar_print(caminho)
            legenda = f"🚨 VAGA LIBERADA: {especialidade}! Corra para o site!"
            if tem_print:
                await telegram.enviar_foto(caminho, legenda)
            else:
                await telegram.enviar_mensagem(legenda)

        await portal.limpar_filtro()


async def monitorar_vagas(settings: Settings) -> None:
    """Ponto de entrada do robô: conecta ao browser e mantém o loop de monitoramento."""
    telegram = TelegramClient(settings.telegram_token, settings.chat_id)
    historico = HistoricoBuscas(settings.arquivo_historico)

    async with async_playwright() as p:
        logger.info("Conectando ao navegador na porta 9222...")
        try:
            browser = await p.chromium.connect_over_cdp(settings.cdp_url)
        except Exception as e:
            logger.error("Erro crítico de conexão com o navegador: %s", e)
            await telegram.enviar_mensagem(f"❌ Erro crítico de conexão com o navegador: {e}")
            await telegram.fechar()
            return

        try:
            context = browser.contexts[0]
            page = next(
                (
                    aba
                    for aba in context.pages
                    if "hspm" in aba.url.lower() or "agendamento" in aba.url.lower()
                ),
                context.pages[0],
            )
            portal = PortalAgendamento(page, settings.url_agendamento)

            await telegram.enviar_mensagem("🤖 Robô iniciado! Monitorando vagas...")
            hora_inicio_sessao = datetime.now()

            while True:
                try:
                    especialidades = carregar_especialidades(settings.arquivo_especialidades)
                    if not especialidades:
                        logger.warning("Lista de especialidades vazia. Aguardando 1 minuto...")
                        await asyncio.sleep(60)
                        continue

                    await page.bring_to_front()
                    if "hspm" not in page.url.lower():
                        await portal.ir_para_agendamento()

                    if await portal.esta_deslogado():
                        logou = await _recuperar_sessao(portal, telegram, settings)
                        if logou:
                            hora_inicio_sessao = datetime.now()
                        continue

                    tempo_online = datetime.now() - hora_inicio_sessao
                    logger.info(
                        "Sessão ativa há %s. Varredura de %d especialidades...",
                        tempo_online,
                        len(especialidades),
                    )

                    await _ciclo_de_busca(portal, telegram, historico, especialidades)

                    logger.info(
                        "Varredura concluída. Dormindo por %d minutos...",
                        settings.tempo_espera_minutos,
                    )
                    await asyncio.sleep(settings.tempo_espera_minutos * 60)

                except Exception as e:
                    # Except amplo intencional: é o loop externo de um robô não
                    # supervisionado — qualquer falha inesperada deve ser
                    # registrada e o ciclo deve seguir, nunca derrubar o processo.
                    logger.error("O robô engasgou, mas não vai desligar: %s", e)
                    await asyncio.sleep(60)
        finally:
            await browser.close()
            await telegram.fechar()

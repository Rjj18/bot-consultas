"""Orquestração do loop de monitoramento: conecta as peças e mantém o robô rodando."""

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright

from .browser import PortalAgendamento
from .config import Settings
from .models import StatusBusca
from .storage import (
    HistoricoBuscas,
    carregar_especialidades,
    carregar_selecionadas,
    salvar_selecionadas,
)
from .telegram_client import TelegramClient

logger = logging.getLogger(__name__)

TAMANHO_PAGINA = 8


@dataclass
class MonitorState:
    """Estado compartilhado entre o controlador do Telegram e a busca."""

    selecionadas: list[str] = field(default_factory=list)
    ativo: bool = True
    ativo_event: asyncio.Event = field(default_factory=asyncio.Event)
    acordar_event: asyncio.Event = field(default_factory=asyncio.Event)

    def __post_init__(self) -> None:
        if self.ativo:
            self.ativo_event.set()

    def iniciar(self) -> None:
        self.ativo = True
        self.ativo_event.set()
        self.acordar_event.set()

    def parar(self) -> None:
        self.ativo = False
        self.ativo_event.clear()
        self.acordar_event.set()

    def filtrar(self, especialidades: list[str]) -> list[str]:
        if not self.selecionadas:
            return especialidades
        selecionadas = set(self.selecionadas)
        filtradas = [
            especialidade for especialidade in especialidades if especialidade in selecionadas
        ]
        return filtradas or especialidades


def _nome_comando(texto: str) -> str:
    comando = texto.split(maxsplit=1)[0].split("@", maxsplit=1)[0].lower()
    return comando.replace("_", "-")


def _teclado_especialidades(
    especialidades: list[str], selecionadas: set[str], pagina: int
) -> dict[str, Any]:
    total_paginas = max(1, (len(especialidades) + TAMANHO_PAGINA - 1) // TAMANHO_PAGINA)
    pagina = max(0, min(pagina, total_paginas - 1))
    inicio = pagina * TAMANHO_PAGINA
    itens = list(enumerate(especialidades[inicio : inicio + TAMANHO_PAGINA], inicio))
    botoes = []
    for posicao in range(0, len(itens), 2):
        linha = []
        for indice, especialidade in itens[posicao : posicao + 2]:
            marcador = "✅" if especialidade in selecionadas else "⬜"
            linha.append(
                {
                    "text": f"{marcador} {indice + 1:02d}",
                    "callback_data": f"esp:t:{indice}",
                }
            )
        botoes.append(linha)
    navegacao: list[dict[str, str]] = []
    if pagina > 0:
        navegacao.append({"text": "◀️ Anterior", "callback_data": f"esp:p:{pagina - 1}"})
    if pagina < total_paginas - 1:
        navegacao.append({"text": "Próxima ▶️", "callback_data": f"esp:p:{pagina + 1}"})
    if navegacao:
        botoes.append(navegacao)
    botoes.append(
        [
            {"text": "✅ Todas", "callback_data": "esp:l"},
            {"text": "✅ Confirmar", "callback_data": "esp:c"},
        ]
    )
    return {"inline_keyboard": botoes}


def _texto_menu(especialidades: list[str], selecionadas: set[str], pagina: int) -> str:
    total = len(especialidades)
    quantidade = len(selecionadas)
    resumo = "todas" if quantidade == total else f"{quantidade} de {total}"
    total_paginas = max(1, (total + TAMANHO_PAGINA - 1) // TAMANHO_PAGINA)
    return (
        f"Especialidades ({resumo} selecionadas)\nPágina {pagina + 1}/{total_paginas}\n\n"
        + "\n".join(
            f"{indice + 1:02d} - {especialidade}"
            for indice, especialidade in enumerate(
                especialidades[
                    pagina * TAMANHO_PAGINA : (pagina + 1) * TAMANHO_PAGINA
                ],
                pagina * TAMANHO_PAGINA,
            )
        )
        + "\n\nToque nos números para alternar a seleção."
    )


async def _recuperar_sessao(
    portal: PortalAgendamento, telegram: TelegramClient, settings: Settings
) -> bool:
    """Fluxo de recuperação de sessão expirada via Telegram. Retorna True se logou."""
    logger.warning("Sessão expirada detectada. Iniciando recuperação via Telegram...")
    caminho_print = Path("print_login.png")

    tem_print = await portal.capturar_print(caminho_print)
    telegram.limpar_respostas()

    if tem_print:
        await telegram.enviar_foto(
            caminho_print, "🚨 A sessão caiu! Digite o texto da imagem para eu logar:"
        )
    else:
        await telegram.enviar_mensagem(
            "🚨 A sessão caiu! (print indisponível) Digite o texto do CAPTCHA:"
        )

    captcha = await telegram.aguardar_resposta()
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
    estado: MonitorState,
) -> None:
    for especialidade in especialidades:
        if not estado.ativo:
            return
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


async def _enviar_menu(
    telegram: TelegramClient,
    especialidades: list[str],
    selecionadas: set[str],
    pagina: int,
    message_id: int | None = None,
) -> int | None:
    texto = _texto_menu(especialidades, selecionadas, pagina)
    teclado = _teclado_especialidades(especialidades, selecionadas, pagina)
    if message_id is None:
        return await telegram.enviar_mensagem(texto, teclado)
    await telegram.editar_mensagem(message_id, texto, teclado)
    return message_id


async def _processar_eventos(
    telegram: TelegramClient,
    settings: Settings,
    estado: MonitorState,
) -> None:
    menu_selecao: set[str] | None = None
    menu_pagina = 0
    menu_message_id: int | None = None
    while True:
        evento = await telegram.aguardar_evento()
        if evento.tipo == "comando":
            comando = _nome_comando(evento.dados["texto"])
            if comando == "/parar":
                estado.parar()
                await telegram.enviar_mensagem(
                    "⏸️ Buscas pausadas. Use /iniciar para retomar."
                )
            elif comando == "/iniciar":
                estado.iniciar()
                await telegram.enviar_mensagem(
                    "▶️ Buscas iniciadas. Uma nova varredura começará agora."
                )
            elif comando == "/especialidades":
                base = carregar_especialidades(settings.arquivo_especialidades)
                menu_selecao = {
                    especialidade
                    for especialidade in estado.selecionadas
                    if especialidade in base
                }
                menu_selecao = menu_selecao or set(base)
                menu_pagina = 0
                menu_message_id = await _enviar_menu(
                    telegram, base, menu_selecao, menu_pagina
                )
            elif comando == "/ajuda":
                await telegram.enviar_mensagem(
                    "Comandos disponíveis:\n"
                    "/iniciar - iniciar as buscas\n"
                    "/parar - pausar as buscas\n"
                    "/especialidades - escolher especialidades\n"
                    "/status - ver o status do monitor"
                )
            elif comando == "/status":
                status = "ativa" if estado.ativo else "pausada"
                await telegram.enviar_mensagem(f"ℹ️ Monitoramento {status}.")
            else:
                await telegram.enviar_mensagem(
                    "Comando não reconhecido. Use /ajuda para ver os comandos."
                )
            continue

        if evento.tipo != "callback":
            continue
        callback_id = evento.dados.get("id", "")
        if callback_id:
            await telegram.responder_callback(callback_id)
        dados = evento.dados.get("dados", "")
        if not isinstance(dados, str) or not dados.startswith("esp:"):
            continue

        base = carregar_especialidades(settings.arquivo_especialidades)
        if menu_selecao is None:
            menu_selecao = set(estado.selecionadas) or set(base)
        partes = dados.split(":")
        if len(partes) == 3 and partes[1] == "t":
            try:
                indice = int(partes[2])
            except ValueError:
                continue
            if 0 <= indice < len(base):
                especialidade = base[indice]
                if especialidade in menu_selecao:
                    menu_selecao.remove(especialidade)
                else:
                    menu_selecao.add(especialidade)
        elif len(partes) == 3 and partes[1] == "p":
            try:
                menu_pagina = int(partes[2])
            except ValueError:
                continue
        elif dados == "esp:l":
            menu_selecao = set(base)
        elif dados == "esp:c":
            estado.selecionadas = [
                especialidade for especialidade in base if especialidade in menu_selecao
            ]
            if len(estado.selecionadas) == len(base):
                estado.selecionadas = []
            salvar_selecionadas(
                settings.arquivo_selecionadas, estado.selecionadas, base
            )
            estado.acordar_event.set()
            await telegram.enviar_mensagem(
                "✅ Seleção salva. Use /iniciar para buscar agora."
            )
            menu_selecao = None
            continue
        if menu_message_id is not None:
            await _enviar_menu(
                telegram, base, menu_selecao, menu_pagina, menu_message_id
            )


async def _loop_monitoramento(
    portal: PortalAgendamento,
    page: Any,
    telegram: TelegramClient,
    historico: HistoricoBuscas,
    settings: Settings,
    estado: MonitorState,
) -> None:
    hora_inicio_sessao = datetime.now()
    while True:
        await estado.ativo_event.wait()
        especialidades_base = carregar_especialidades(settings.arquivo_especialidades)
        especialidades = estado.filtrar(especialidades_base)
        if not especialidades:
            logger.warning("Lista de especialidades vazia. Aguardando 1 minuto...")
            estado.acordar_event.clear()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(estado.acordar_event.wait(), timeout=60)
            continue

        await page.bring_to_front()
        if not await portal.esta_na_pagina_de_agendamento():
            logger.info("Página incorreta. Navegando para a página correta.")
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
        await _ciclo_de_busca(portal, telegram, historico, especialidades, estado)
        logger.info("Varredura concluída. Aguardando próxima busca...")
        estado.acordar_event.clear()
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(
                estado.acordar_event.wait(), timeout=settings.tempo_espera_minutos * 60
            )


async def monitorar_vagas(settings: Settings) -> None:
    """Ponto de entrada do robô: conecta ao browser e mantém o loop de monitoramento."""
    telegram = TelegramClient(settings.telegram_token, settings.chat_id)
    historico = HistoricoBuscas(settings.arquivo_historico)
    base = carregar_especialidades(settings.arquivo_especialidades)
    estado = MonitorState(carregar_selecionadas(settings.arquivo_selecionadas, base))

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

            await telegram.iniciar_polling()
            await telegram.configurar_comandos()
            await telegram.enviar_mensagem("🤖 Robô iniciado! Monitorando vagas...")
            tarefa_comandos = asyncio.create_task(_processar_eventos(telegram, settings, estado))
            try:
                await _loop_monitoramento(portal, page, telegram, historico, settings, estado)
            except Exception as e:
                logger.error("O robô engasgou, mas não vai desligar: %s", e)
            finally:
                tarefa_comandos.cancel()
                await asyncio.gather(tarefa_comandos, return_exceptions=True)
        finally:
            await browser.close()
            await telegram.fechar()

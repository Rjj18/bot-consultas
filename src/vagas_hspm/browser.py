"""Interações com a página do portal de agendamento via Playwright."""

import contextlib
import logging
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from playwright.async_api import Locator, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .models import StatusBusca

logger = logging.getLogger(__name__)

SELETOR_BOTAO_ENTRAR = "button:has-text('ENTRAR')"


class VagaDetalhada(TypedDict):
    mes: str
    data: str
    quantidade: str
    horario: str
    medico: str


class PortalAgendamento:
    """Encapsula toda a manipulação da página do portal (Playwright).

    Mantém a checagem de sessão em dois modos, replicando o comportamento
    original com propósito:
    - `esta_deslogado()`: usada uma vez por ciclo do loop principal, espera
      até 5s o botão de login aparecer antes de decidir. É a checagem "cara",
      mas confiável, usada quando ainda não sabemos o estado da sessão.
    - `deslogou_agora()`: usada dentro da varredura de especialidades, checa
      instantaneamente sem esperar — mais barata, porque nesse ponto já
      sabíamos que a sessão estava ativa no início do ciclo.
    """

    def __init__(self, page: Page, url_agendamento: str) -> None:
        self._page = page
        self._url = url_agendamento

    async def _botao_entrar_visivel(self, aguardar: bool) -> bool:
        botao = self._page.locator(SELETOR_BOTAO_ENTRAR).first
        if aguardar:
            with contextlib.suppress(PlaywrightTimeoutError):
                await botao.wait_for(state="visible", timeout=5000)
        return await botao.is_visible()

    async def esta_deslogado(self) -> bool:
        return await self._botao_entrar_visivel(aguardar=True)

    async def deslogou_agora(self) -> bool:
        return await self._botao_entrar_visivel(aguardar=False)

    async def capturar_print(self, caminho: Path) -> bool:
        """Tenta capturar a tela cheia; cai para print do body se falhar.

        Playwright pode falhar de formas variadas aqui (timeout, elemento
        detached, página navegando no meio do print) — por isso o except
        amplo é intencional: qualquer falha de print não deve derrubar o
        robô, só deve ser registrada e seguir sem a imagem.
        """
        try:
            await self._page.evaluate("window.stop()")
            await self._page.bring_to_front()
            await self._page.wait_for_timeout(1000)
            await self._page.screenshot(path=str(caminho), timeout=10000)
            return True
        except Exception as e:
            logger.warning("Print da tela cheia falhou (%s); tentando print do body.", e)
            try:
                await self._page.locator("body").screenshot(path=str(caminho), timeout=5000)
                return True
            except Exception:
                logger.error("Print completamente indisponível.")
                return False

    async def fazer_login(self, cpf: str | None, senha: str | None, captcha: str) -> None:
        if cpf and senha:
            campo_cpf = self._page.locator("input.rz-textbox").nth(0)
            campo_senha = self._page.locator("input.rz-textbox").nth(1)
            await campo_cpf.click()
            await campo_cpf.clear()
            await campo_cpf.press_sequentially(cpf, delay=100)
            await campo_senha.click()
            await campo_senha.clear()
            await campo_senha.fill(senha)

        campo_captcha = self._page.get_by_placeholder("Digite o Texto da Imagem", exact=False).first
        await campo_captcha.fill(captcha)
        await self._page.locator(SELETOR_BOTAO_ENTRAR).first.click()
        await self._page.wait_for_timeout(5000)

    async def esta_na_pagina_de_agendamento(self) -> bool:
        """Retorna True quando a página atual parece ser a do portal de agendamento."""
        url_atual = (self._page.url or "").lower()
        url_esperada = self._url.lower()
        return "hspm" in url_atual or "agendamento" in url_atual or url_esperada in url_atual

    async def ir_para_agendamento(self) -> None:
        await self._page.goto(self._url)
        await self._page.wait_for_load_state("networkidle")

    async def buscar_especialidade(self, especialidade: str) -> StatusBusca:
        """Seleciona a especialidade e pesquisa; retorna se há vaga disponível."""
        await self._page.bring_to_front()
        await self._page.locator("label.rz-dropdown-label").first.click(timeout=5000)
        await self._page.wait_for_timeout(500)
        await self._page.get_by_text(especialidade, exact=True).first.click(timeout=5000)
        await self._page.locator("button:has-text('Pesquisar')").first.click(timeout=5000)

        botao_ok = self._page.locator("button:has-text('OK')").first
        try:
            # Se o botão OK aparece, é o popup de "sem vagas" confirmando a busca.
            await botao_ok.wait_for(state="visible", timeout=5000)
            await botao_ok.click()
            await self._page.wait_for_timeout(500)
            return StatusBusca.SEM_VAGA
        except PlaywrightTimeoutError:
            # Sem o popup de "sem vagas", assumimos que a busca retornou horários.
            return StatusBusca.VAGA_ENCONTRADA

    async def limpar_filtro(self) -> None:
        try:
            await self._page.locator("button:has-text('Limpar')").first.click(timeout=5000)
            await self._page.wait_for_timeout(1000)
        except PlaywrightTimeoutError:
            await self._page.reload()
            await self._page.wait_for_load_state("networkidle")

    async def mapear_vagas_dois_meses(self) -> list[VagaDetalhada]:
        """Mapeia as vagas exibidas no mês atual e no mês seguinte."""
        agora = datetime.now()
        meses = (agora.month, agora.month % 12 + 1)
        nomes_meses = (
            "janeiro",
            "fevereiro",
            "março",
            "abril",
            "maio",
            "junho",
            "julho",
            "agosto",
            "setembro",
            "outubro",
            "novembro",
            "dezembro",
        )
        resultados: list[VagaDetalhada] = []

        for indice_mes, numero_mes in enumerate(meses):
            resultados.extend(
                await self._mapear_vagas_mes(nomes_meses[numero_mes - 1])
            )
            if indice_mes == 0:
                botao_proximo = self._page.locator("button.rz-next").first
                await botao_proximo.wait_for(state="visible", timeout=5000)
                await botao_proximo.scroll_into_view_if_needed()
                await botao_proximo.click()
                await self._page.wait_for_timeout(1500)

        return resultados

    async def _mapear_vagas_mes(self, mes: str) -> list[VagaDetalhada]:
        calendario = self._page.locator(".rz-scheduler")
        eventos = calendario.locator(".rz-event-content")
        resultados: list[VagaDetalhada] = []

        for indice in range(await eventos.count()):
            evento = eventos.nth(indice)
            quantidade = (await evento.inner_text()).strip()
            dia = await self._extrair_dia_da_vaga(evento)
            await evento.click()

            tabela = self._page.locator(".rz-grid-table")
            await tabela.wait_for(state="visible")
            linha = tabela.locator("tbody tr").first
            await linha.wait_for(state="visible")
            colunas = linha.locator("td")
            resultados.append(
                {
                    "mes": mes,
                    "data": f"{dia} de {mes}",
                    "quantidade": quantidade,
                    "horario": (await colunas.nth(1).inner_text()).strip(),
                    "medico": (await colunas.nth(5).inner_text()).strip(),
                }
            )

            await self._page.keyboard.press("Escape")
            await calendario.wait_for(state="visible")

        return resultados

    async def _extrair_dia_da_vaga(self, evento: Locator) -> str:
        titulo_do_dia = evento.locator(
            "xpath=ancestor::*[.//div[contains(@class, 'rz-slot-title')]][1]"
        ).locator(".rz-slot-title").first
        return (await titulo_do_dia.inner_text()).strip()

import asyncio
from datetime import datetime
from typing import cast

from playwright.async_api import Page

from vagas_hspm.browser import PortalAgendamento


class FakeLocator:
    def __init__(self, page: "FakePage", tipo: str, indice: int = 0) -> None:
        self.page = page
        self.tipo = tipo
        self.indice = indice

    @property
    def first(self) -> "FakeLocator":
        if self.tipo in ("slot", "dia"):
            return self
        return FakeLocator(self.page, self.tipo, 0)

    def locator(self, seletor: str) -> "FakeLocator":
        if self.tipo == "evento" and seletor.startswith("xpath="):
            return FakeLocator(self.page, "slot", self.indice)
        if self.tipo == "slot" and seletor == ".rz-slot-title":
            return FakeLocator(self.page, "dia", self.indice)
        if self.tipo == "calendario":
            return FakeLocator(self.page, "eventos")
        if self.tipo == "tabela" and seletor == "tbody tr":
            return FakeLocator(self.page, "linha")
        if self.tipo == "linha" and seletor == "td":
            return FakeLocator(self.page, "colunas")
        raise AssertionError(f"Seletor inesperado: {seletor}")

    def nth(self, indice: int) -> "FakeLocator":
        if self.tipo == "eventos":
            return FakeLocator(self.page, "evento", indice)
        if self.tipo == "colunas":
            tipo = {0: "data", 1: "celula", 5: "medico"}.get(indice, "medico")
            return FakeLocator(self.page, tipo, indice)
        return FakeLocator(self.page, self.tipo, indice)

    async def count(self) -> int:
        if self.tipo != "eventos":
            raise AssertionError("count inesperado")
        return (2, 1)[self.page.mes]

    async def inner_text(self) -> str:
        if self.tipo == "evento":
            return ("1 vagas", "2 vagas")[self.indice]
        if self.tipo == "data":
            datas = (("18/09/2026", "19/09/2026"), ("02/10/2026",))
            return datas[self.page.mes][self.page.evento]
        if self.tipo == "dia":
            dias = (("18", "19"), ("02",))
            return dias[self.page.mes][self.indice]
        if self.tipo == "celula":
            return ("10:00", "11:30")[self.page.mes]
        if self.tipo == "medico":
            return ("Dra. A", "Dr. B")[self.page.mes]
        raise AssertionError("inner_text inesperado")

    async def click(self) -> None:
        if self.tipo == "evento":
            self.page.tabela_aberta = True
            self.page.evento = self.indice
        elif self.tipo == "proximo":
            self.page.mes = 1
        else:
            raise AssertionError("click inesperado")

    async def wait_for(self, state: str = "visible", timeout: int | None = None) -> None:
        assert state == "visible"
        assert timeout in (None, 5000)

    async def scroll_into_view_if_needed(self) -> None:
        return None


class FakePage:
    def __init__(self) -> None:
        self.mes = 0
        self.evento = 0
        self.tabela_aberta = False
        self.escapes = 0
        self.keyboard = self

    def locator(self, seletor: str) -> FakeLocator:
        if seletor == ".rz-scheduler":
            return FakeLocator(self, "calendario")
        if seletor == ".rz-grid-table":
            return FakeLocator(self, "tabela")
        if seletor == "button.rz-next":
            return FakeLocator(self, "proximo")
        raise AssertionError(f"Seletor inesperado: {seletor}")

    async def press(self, tecla: str) -> None:
        assert tecla == "Escape"
        self.escapes += 1
        self.tabela_aberta = False

    async def wait_for_timeout(self, tempo: int) -> None:
        assert tempo == 1500


def test_mapeia_vagas_do_mes_atual_e_subsequente() -> None:
    async def executar() -> None:
        page = FakePage()
        portal = PortalAgendamento(cast(Page, page), "https://example.test")

        resultado = await portal.mapear_vagas_dois_meses()
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
        mes_atual = nomes_meses[datetime.now().month - 1]
        mes_seguinte = nomes_meses[datetime.now().month % 12]

        assert resultado == [
            {
                "mes": mes_atual,
                "data": f"18 de {mes_atual}",
                "quantidade": "1 vagas",
                "horario": "10:00",
                "medico": "Dra. A",
            },
            {
                "mes": mes_atual,
                "data": f"19 de {mes_atual}",
                "quantidade": "2 vagas",
                "horario": "10:00",
                "medico": "Dra. A",
            },
            {
                "mes": mes_seguinte,
                "data": f"02 de {mes_seguinte}",
                "quantidade": "1 vagas",
                "horario": "11:30",
                "medico": "Dr. B",
            },
        ]
        assert page.escapes == 3

    asyncio.run(executar())
from datetime import datetime

from vagas_hspm.browser import PortalAgendamento


class FakeLocator:
    def __init__(self, page: "FakePage", selector: str, index: int | None = None) -> None:
        self.page = page
        self.selector = selector
        self.index = index

    @property
    def first(self) -> "FakeLocator":
        return FakeLocator(self.page, self.selector, 0)

    def locator(self, selector: str) -> "FakeLocator":
        return FakeLocator(self.page, f"{self.selector} {selector}")

    def nth(self, index: int) -> "FakeLocator":
        return FakeLocator(self.page, self.selector, index)

    async def wait_for(self, state: str) -> None:
        assert state == "visible"

    async def count(self) -> int:
        if self.selector == ".rz-scheduler .rz-event-content":
            return len(self.page.months[self.page.month_index]["events"])
        return 1

    async def inner_text(self) -> str:
        if self.selector == ".rz-scheduler .rz-event-content":
            return self.page.months[self.page.month_index]["events"][self.index or 0][0]
        if self.selector.endswith("tbody tr td"):
            row = self.page.months[self.page.month_index]["events"][self.page.event_index][1]
            return row[self.index or 0]
        raise AssertionError(f"Selector inesperado: {self.selector}")

    async def click(self, **kwargs: object) -> None:
        if self.selector == "button.rz-next":
            self.page.month_index += 1
        elif self.selector == ".rz-scheduler .rz-event-content":
            self.page.event_index = self.index or 0

    async def focus(self) -> None:
        return None


class FakeKeyboard:
    async def press(self, key: str) -> None:
        assert key == "Escape"


class FakePage:
    def __init__(self) -> None:
        self.month_index = 0
        self.event_index = 0
        self.keyboard = FakeKeyboard()
        self.months = [
            {"events": [("1 vagas", ["", "08:30", "", "", "", "Dra. Atual"])]},
            {"events": [("2 vagas", ["", "14:10", "", "", "", "Dr. Seguinte"])]},
        ]

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self, selector)

    async def wait_for_timeout(self, timeout: int) -> None:
        assert timeout == 1500


def test_mapear_vagas_mapeia_dois_meses() -> None:
    async def executar() -> None:
        portal = PortalAgendamento(FakePage(), "https://example.test")

        resultado = await portal.mapear_vagas(datetime(2026, 9, 17))

        assert resultado == [
            {
                "mes": "setembro",
                "quantidade": "1 vagas",
                "horario": "08:30",
                "medico": "Dra. Atual",
            },
            {
                "mes": "outubro",
                "quantidade": "2 vagas",
                "horario": "14:10",
                "medico": "Dr. Seguinte",
            },
        ]

    import asyncio

    asyncio.run(executar())

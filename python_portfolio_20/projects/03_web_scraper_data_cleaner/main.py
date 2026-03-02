from __future__ import annotations

from html.parser import HTMLParser


class TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_td = False
        self.current: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == 'td':
            self.in_td = True

    def handle_endtag(self, tag: str) -> None:
        if tag == 'td':
            self.in_td = False
        if tag == 'tr' and self.current:
            self.rows.append(self.current)
            self.current = []

    def handle_data(self, data: str) -> None:
        if self.in_td:
            self.current.append(data.strip())


def clean_price(raw: str) -> float:
    return float(raw.replace('$', '').replace(',', ''))


def run_demo() -> dict[str, object]:
    html = '<table><tr><td>BTC</td><td>$102,500.15</td></tr></table>'
    parser = TableParser()
    parser.feed(html)
    symbol, price = parser.rows[0]
    return {'project': 'web_scraper_data_cleaner', 'symbol': symbol, 'price': clean_price(price)}


if __name__ == '__main__':
    print(run_demo())

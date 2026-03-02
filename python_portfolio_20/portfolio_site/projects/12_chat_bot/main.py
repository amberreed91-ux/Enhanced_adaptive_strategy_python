from __future__ import annotations


class Bot:
    def __init__(self) -> None:
        self.state: dict[str, int] = {}

    def handle(self, user: str, command: str) -> str:
        if command == '/start':
            self.state[user] = 0
            return 'session started'
        if command == '/ping':
            self.state[user] = self.state.get(user, 0) + 1
            return f'pong {self.state[user]}'
        return 'unknown command'


def run_demo() -> dict[str, object]:
    bot = Bot()
    bot.handle('amber', '/start')
    second = bot.handle('amber', '/ping')
    return {'project': 'chat_bot', 'last_reply': second}


if __name__ == '__main__':
    print(run_demo())

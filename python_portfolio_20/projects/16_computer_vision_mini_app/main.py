from __future__ import annotations


def blur_1d(row: list[int]) -> list[int]:
    if len(row) < 3:
        return row[:]
    out = [row[0]]
    for i in range(1, len(row) - 1):
        out.append((row[i - 1] + row[i] + row[i + 1]) // 3)
    out.append(row[-1])
    return out


def edge_1d(row: list[int]) -> list[int]:
    return [abs(row[i + 1] - row[i]) for i in range(len(row) - 1)]


def run_demo() -> dict[str, object]:
    pixels = [10, 12, 19, 24, 18]
    return {'project': 'computer_vision_mini_app', 'blur': blur_1d(pixels), 'edge': edge_1d(pixels)}


if __name__ == '__main__':
    print(run_demo())

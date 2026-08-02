from collections import Counter

from erudit.config import DEFAULT_TILESET, load_tileset


def test_load_default_tileset():
    ts = load_tileset(DEFAULT_TILESET)
    assert ts.id == "scrabble_ru"
    assert ts.board_size == 15
    assert ts.rack_size == 7
    assert ts.center == (7, 7)
    assert ts.bingo_bonus == 0


def test_total_tiles_is_104():
    ts = load_tileset()
    assert sum(spec.count for spec in ts.tiles) == 102
    assert ts.blank_count == 2
    assert ts.total_tiles == 104


def test_board_is_15x15():
    ts = load_tileset()
    assert len(ts.board) == 15
    assert all(len(row) == 15 for row in ts.board)


def test_bonus_distribution_is_classic():
    ts = load_tileset()
    counts = Counter("".join(ts.board))
    assert counts["T"] == 8
    assert counts["D"] == 16
    assert counts["*"] == 1
    assert counts["t"] == 12
    assert counts["d"] == 24


def test_board_is_symmetric_about_center():
    ts = load_tileset()
    n = ts.board_size
    for r in range(n):
        for c in range(n):
            cell = ts.board[r][c]
            # центр — единственная клетка, не имеющая пары
            expected = cell if cell != "*" else "*"
            assert ts.board[r][n - 1 - c] == expected, f"по горизонтали ({r},{c})"
            assert ts.board[n - 1 - r][c] == expected, f"по вертикали ({r},{c})"


def test_multipliers():
    ts = load_tileset()
    assert ts.word_multiplier(0, 0) == 3
    assert ts.word_multiplier(7, 7) == 2
    assert ts.word_multiplier(7, 8) == 1
    assert ts.letter_multiplier(0, 3) == 2
    assert ts.letter_multiplier(1, 5) == 3
    assert ts.letter_multiplier(0, 0) == 1


def test_value_of_letter():
    ts = load_tileset()
    assert ts.value_of("О") == 1
    assert ts.value_of("Ъ") == 10

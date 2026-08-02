import random

from erudit.config import load_tileset
from erudit.tiles import Bag, Tile, build_tiles


def test_full_set_has_104_unique_tiles():
    tiles = build_tiles(load_tileset())
    assert len(tiles) == 104
    assert len({t.id for t in tiles}) == 104
    assert sum(1 for t in tiles if t.is_blank) == 2


def test_blank_is_worth_zero():
    tiles = build_tiles(load_tileset())
    assert all(t.value == 0 for t in tiles if t.is_blank)


def test_draw_reduces_bag():
    bag = Bag(build_tiles(load_tileset()), random.Random(1))
    assert len(bag) == 104
    drawn = bag.draw(7)
    assert len(drawn) == 7
    assert len(bag) == 97


def test_draw_from_empty_bag_returns_empty_list():
    bag = Bag([], random.Random(1))
    assert bag.draw(7) == []
    assert len(bag) == 0


def test_draw_more_than_available_returns_the_rest():
    tiles = [Tile(id=i, letter="А", value=1) for i in range(3)]
    bag = Bag(tiles, random.Random(1))
    assert len(bag.draw(7)) == 3
    assert len(bag) == 0


def test_same_seed_gives_same_sequence():
    ts = load_tileset()
    first = Bag(build_tiles(ts), random.Random(42)).draw(20)
    second = Bag(build_tiles(ts), random.Random(42)).draw(20)
    assert [t.id for t in first] == [t.id for t in second]


def test_different_seed_gives_different_sequence():
    ts = load_tileset()
    first = Bag(build_tiles(ts), random.Random(1)).draw(20)
    second = Bag(build_tiles(ts), random.Random(2)).draw(20)
    assert [t.id for t in first] != [t.id for t in second]


def test_put_back_returns_tiles_to_the_bag():
    bag = Bag(build_tiles(load_tileset()), random.Random(3))
    drawn = bag.draw(7)
    bag.put_back(drawn)
    assert len(bag) == 104
    assert {t.id for t in bag.tiles()} >= {t.id for t in drawn}

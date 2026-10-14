"""Итоги партии. Считаются по журналу — отдельно ничего не хранится."""

from __future__ import annotations

from erudit.game import Game


def summarize(game: Game) -> dict:
    players = {
        player.id: {
            "id": player.id,
            "name": player.name,
            "score": player.score,
            "moves": 0,
            "points": 0,
            "best": None,
            "longest": None,
            "bingos": 0,
            "passes": 0,
            "exchanges": 0,
        }
        for player in game.players
    }
    order = [player.id for player in game.players]
    running = dict.fromkeys(order, 0)
    timeline = [[0] * len(order)]

    for entry in game.log:
        stats = players.get(entry.get("player"))
        if stats is None:
            continue
        kind = entry["type"]
        if kind == "move":
            score = entry["score"]
            stats["moves"] += 1
            stats["points"] += score
            running[stats["id"]] += score
            words = [word for word, _ in entry.get("words", [])]
            if stats["best"] is None or score > stats["best"]["score"]:
                stats["best"] = {"words": words, "score": score}
            for word in words:
                if stats["longest"] is None or len(word) > len(stats["longest"]):
                    stats["longest"] = word
            # в старых журналах числа фишек нет — такие ходы бинго не считаются
            if entry.get("tiles") == game.tileset.rack_size:
                stats["bingos"] += 1
        elif kind == "pass":
            stats["passes"] += 1
        elif kind == "exchange":
            stats["exchanges"] += 1
        else:
            continue
        timeline.append([running[player_id] for player_id in order])

    # штрафы за остаток стойки в конце меняют счёт без хода — отдельной точкой
    final = [players[player_id]["score"] for player_id in order]
    if final != timeline[-1]:
        timeline.append(final)

    for stats in players.values():
        stats["average"] = round(stats["points"] / stats["moves"], 1) if stats["moves"] else 0
    return {"players": [players[player_id] for player_id in order], "timeline": timeline}

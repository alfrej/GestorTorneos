from __future__ import annotations

from itertools import combinations
import random


def build_schedule_report(participants, courts, rounds, shuffle=False):
    data = generate_schedule(participants, courts, rounds, shuffle=shuffle)
    if data["error"]:
        return data["error"]
    return format_schedule(data)


def build_schedule_data(participants, courts, rounds, shuffle=False):
    return generate_schedule(participants, courts, rounds, shuffle=shuffle)


def generate_schedule(participants, courts, rounds, shuffle=False):
    names = list(participants)
    if shuffle:
        random.shuffle(names)
    n = len(names)
    if n < 4:
        return {"error": "Se necesitan al menos 4 participantes para generar partidos."}
    if courts < 1 or rounds < 1:
        return {"error": "El numero de pistas y rondas debe ser al menos 1."}

    max_matches_per_round = min(courts, n // 4)
    if max_matches_per_round == 0:
        return {"error": "No hay suficientes participantes para formar un partido."}

    partner_counts = {pair: 0 for pair in combinations(range(n), 2)}
    opponent_counts = {pair: 0 for pair in combinations(range(n), 2)}
    team_counts = {pair: 0 for pair in combinations(range(n), 2)}
    match_counts = {}

    matches_played = [0] * n
    rests = [0] * n
    player_logs = {i: [] for i in range(n)}
    player_rest_rounds = {i: [] for i in range(n)}
    rounds_out = []

    for round_index in range(1, rounds + 1):
        missing_by_player = _missing_partner_counts(n, partner_counts)
        play_slots = max_matches_per_round * 4
        sorted_players = sorted(
            range(n),
            key=lambda i: (-missing_by_player[i], matches_played[i], -rests[i], names[i]),
        )
        play_count = min(play_slots, (n // 4) * 4)
        playing = set(sorted_players[:play_count])
        remaining = set(playing)

        round_matches = []
        unmet_exists = any(count == 0 for count in partner_counts.values())

        while len(remaining) >= 4:
            best = None
            best_score = None
            for combo in combinations(sorted(remaining), 4):
                pairings = (
                    ((combo[0], combo[1]), (combo[2], combo[3])),
                    ((combo[0], combo[2]), (combo[1], combo[3])),
                    ((combo[0], combo[3]), (combo[1], combo[2])),
                )
                for team1, team2 in pairings:
                    team1 = tuple(sorted(team1))
                    team2 = tuple(sorted(team2))
                    score = _score_match(
                        team1,
                        team2,
                        partner_counts,
                        opponent_counts,
                        team_counts,
                        match_counts,
                        matches_played,
                        rests,
                        unmet_exists,
                    )
                    match_key = _match_key(team1, team2)
                    tie_break = (match_key[0], match_key[1])
                    if best_score is None or score > best_score:
                        best = (team1, team2, tie_break)
                        best_score = score
                    elif score == best_score and best is not None:
                        if tie_break < best[2]:
                            best = (team1, team2, tie_break)
            if best is None:
                break

            team1, team2, _ = best
            for player in team1 + team2:
                remaining.remove(player)
                matches_played[player] += 1

            partner_counts[team1] += 1
            partner_counts[team2] += 1
            team_counts[team1] += 1
            team_counts[team2] += 1

            for a in team1:
                for b in team2:
                    opponent_counts[_pair_key(a, b)] += 1

            match_key = _match_key(team1, team2)
            match_counts[match_key] = match_counts.get(match_key, 0) + 1
            round_matches.append((team1, team2))

            for player in team1:
                teammate = team1[0] if team1[1] == player else team1[1]
                player_logs[player].append((round_index, teammate, team2))
            for player in team2:
                teammate = team2[0] if team2[1] == player else team2[1]
                player_logs[player].append((round_index, teammate, team1))

        resting = sorted(set(range(n)) - playing | remaining)
        for player in resting:
            rests[player] += 1
            player_rest_rounds[player].append(round_index)

        rounds_out.append(
            {
                "round": round_index,
                "matches": round_matches,
                "resting": resting,
            }
        )

    unmet_pairs = [pair for pair, count in partner_counts.items() if count == 0]
    return {
        "error": None,
        "names": names,
        "rounds": rounds_out,
        "player_logs": player_logs,
        "player_rest_rounds": player_rest_rounds,
        "matches_played": matches_played,
        "rests": rests,
        "unmet_pairs": unmet_pairs,
    }


def format_schedule(data):
    names = data["names"]
    lines = []
    for round_data in data["rounds"]:
        lines.append(f"Ronda {round_data['round']}")
        if round_data["matches"]:
            for idx, match in enumerate(round_data["matches"], 1):
                team1, team2 = match
                team1_names = f"{names[team1[0]]} + {names[team1[1]]}"
                team2_names = f"{names[team2[0]]} + {names[team2[1]]}"
                lines.append(f"- Partido {idx}: ({team1_names}) vs ({team2_names})")
        else:
            lines.append("- Sin partidos")

        if round_data["resting"]:
            rest_names = ", ".join(names[i] for i in round_data["resting"])
            lines.append(f"- Descansan: {rest_names}")
        else:
            lines.append("- Descansan: nadie")
        lines.append("")

    lines.append("Resumen jugadores")
    for idx, name in enumerate(names):
        lines.append(
            f"- {name}: juega {data['matches_played'][idx]} partidos; "
            f"descansa {data['rests'][idx]} rondas."
        )

    if data["unmet_pairs"]:
        lines.append("")
        lines.append(
            "Aviso: no se pudo completar todas las parejas unicas con las rondas indicadas."
        )

    return "\n".join(lines)


def _pair_key(a, b):
    return (a, b) if a < b else (b, a)


def _match_key(team1, team2):
    return (team1, team2) if team1 < team2 else (team2, team1)


def _missing_partner_counts(n, partner_counts):
    missing = [0] * n
    for i in range(n):
        for j in range(i + 1, n):
            if partner_counts[(i, j)] == 0:
                missing[i] += 1
                missing[j] += 1
    return missing


def _score_match(
    team1,
    team2,
    partner_counts,
    opponent_counts,
    team_counts,
    match_counts,
    matches_played,
    rests,
    unmet_exists,
):
    new_partner = int(partner_counts[team1] == 0) + int(partner_counts[team2] == 0)
    partner_repeat = partner_counts[team1] + partner_counts[team2]

    new_opponent = 0
    opponent_repeat = 0
    for a in team1:
        for b in team2:
            if opponent_counts[_pair_key(a, b)] == 0:
                new_opponent += 1
            else:
                opponent_repeat += 1

    team_repeat = team_counts[team1] + team_counts[team2]
    match_repeat = match_counts.get(_match_key(team1, team2), 0)
    balance = sum(rests[p] - matches_played[p] for p in team1 + team2)

    score = (
        new_partner * 100
        + new_opponent * 10
        + balance * 0.5
        - opponent_repeat * 2
        - partner_repeat * 5
        - team_repeat * 15
        - match_repeat * 30
    )
    if unmet_exists and new_partner == 0:
        score -= 40
    return score


if __name__ == "__main__":
    sample_players = ["Ana", "Beto", "Carla", "Dani", "Eva", "Fran", "Gema", "Hugo"]
    report = build_schedule_report(sample_players, courts=2, rounds=3)
    print(report)

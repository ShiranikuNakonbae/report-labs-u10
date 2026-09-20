"""Parse a baseball scorer "REPORT PERTANDINGAN" PDF into structured statistics.

The PDF format is a set of games. Each game block contains:

    GAME N
    AWAY at HOME
    Score By Innings 1 2 3 ... R H E
    AWAY <runs per inning> <R> <H> <E>
    HOME <runs per inning> <R> <H> <E>
    ...
    AWAY R, HOME R
    AWAY HOME
      ab r h bi   ab r h bi
    <away players ...>  <home players ...>
    TEAM TOTALS ...
    E: <errors> ... LOB: ...
    <pitching>
    T: ...
    <play-by-play innings>
"""

from collections import Counter, defaultdict
import re

from pypdf import PdfReader


INNING_HEADER_RE = re.compile(
    r"^(?P<team>.+?) - (Top|Bottom) of the (?P<inning>\d+)(?:st|nd|rd|th):"
)


def extract_text(pdf_path):
    reader = PdfReader(str(pdf_path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def split_game_blocks(text):
    """Return a list of (game_number, block_text) tuples."""
    blocks = []
    current = []
    current_num = None
    for line in text.splitlines():
        m = re.match(r"^GAME\s+(\d+)\s*$", line.strip())
        if m:
            if current_num is not None:
                blocks.append((current_num, "\n".join(current)))
            current_num = int(m.group(1))
            current = []
        elif current_num is not None:
            current.append(line)
    if current_num is not None:
        blocks.append((current_num, "\n".join(current)))
    return blocks


def _score_tail(line, team):
    """Extract (R, H, E) from a 'TEAM <runs...> <R> <H> <E>' line."""
    stripped = line.strip()
    if stripped.startswith(team):
        rest = stripped[len(team):].split()
    else:
        # Fall back to last three tokens if name spacing differs.
        rest = stripped.split()
    return int(rest[-3]), int(rest[-2]), int(rest[-1])


def _parse_box_entries(line):
    """Parse one box-score row into zero, one or two player entries.

    Each entry is "<NAME> <POS> <ab> <r> <h> <bi>". Names are letters/spaces
    only; the position is the single token immediately before the four stats.
    """
    tokens = line.split()
    entries = []
    i = 0
    n = len(tokens)
    while i + 4 <= n:
        found = -1
        for j in range(i, n - 3):
            if all(tokens[k].isdigit() for k in range(j, j + 4)):
                found = j
                break
        if found == -1 or found == 0:
            break
        name = " ".join(tokens[i:found - 1])
        pos = tokens[found - 1]
        ab, runs, hits, rbi = (int(tokens[found + k]) for k in range(4))
        entries.append({
            "player": name,
            "pos": pos,
            "ab": ab,
            "runs": runs,
            "hits": hits,
            "rbi": rbi,
        })
        i = found + 4
    return entries


def parse_error_count(error_text, player):
    """Count defensive errors for a player from the 'E:' section."""
    match = re.search(r"(?<![A-Z])" + re.escape(player) + r"(?:\((\d+)\))?", error_text)
    if not match:
        return 0
    return int(match.group(1)) if match.group(1) else 1


def _play_by_play_section(block):
    """Return the play-by-play lines (starting at the first inning header)."""
    lines = block.splitlines()
    for i, line in enumerate(lines):
        if INNING_HEADER_RE.match(line.strip()):
            return lines[i:]
    return []


def parse_play_by_play(block, player_names):
    """Compute per-player pa, on_base, hit_score sum and total_bases."""
    names_sorted = sorted(player_names, key=len, reverse=True)
    pa = Counter()
    on_base = Counter()
    hit_score = Counter()
    total_bases = Counter()

    for line in _play_by_play_section(block):
        player = next(
            (name for name in names_sorted if line.startswith(name + " ")),
            None,
        )
        if not player:
            continue

        lowered = line.lower()
        pa[player] += 1

        reached = (
            "home run" in lowered
            or "tripled" in lowered
            or "doubled" in lowered
            or "singled" in lowered
            or "reached on error" in lowered
            or "reached on fielder's choice" in lowered
            or "hit by pitch" in lowered
            or "walked" in lowered
        )
        if reached:
            on_base[player] += 1

        if "home run" in lowered:
            hit_score[player] += 100
            total_bases[player] += 4
        elif "tripled" in lowered:
            hit_score[player] += 90
            total_bases[player] += 3
        elif "doubled" in lowered:
            hit_score[player] += 80
            total_bases[player] += 2
        elif "singled" in lowered:
            hit_score[player] += 70
            total_bases[player] += 1
        elif "hit by pitch" in lowered:
            hit_score[player] += 70
        elif "reached on" in lowered:
            hit_score[player] += 50
        elif "struck out" in lowered:
            hit_score[player] += 40
        else:
            hit_score[player] += 50

    return pa, on_base, hit_score, total_bases


def parse_game(block, game_num):
    lines = block.splitlines()

    matchup = next(
        (ln.strip() for ln in lines if " at " in ln and "Score By Innings" not in ln),
        "",
    )
    away, home = [part.strip() for part in matchup.split(" at ", 1)]

    score_idx = next(
        (i for i, ln in enumerate(lines) if ln.strip().startswith("Score By Innings")),
        None,
    )
    if score_idx is not None and score_idx + 2 < len(lines):
        away_r, away_h, away_e = _score_tail(lines[score_idx + 1], away)
        home_r, home_h, home_e = _score_tail(lines[score_idx + 2], home)
    else:
        away_r = away_h = away_e = home_r = home_h = home_e = 0

    # Box score player region.
    box_idx = next(
        (i for i, ln in enumerate(lines) if "ab r h bi" in ln),
        None,
    )
    players = []
    if box_idx is not None:
        # Box-score columns are ordered winner-first, not away-first.
        # The header line just above "ab r h bi" lists the teams in the
        # same order as the left/right columns.
        left_team, right_team = away, home
        if box_idx > 0:
            header = lines[box_idx - 1].strip()
            if header == f"{away} {home}":
                left_team, right_team = away, home
            elif header == f"{home} {away}":
                left_team, right_team = home, away

        totals_idx = next(
            (i for i in range(box_idx + 1, len(lines)) if "TEAM TOTALS" in lines[i]),
            len(lines),
        )
        for line in lines[box_idx + 1:totals_idx]:
            if not line.strip():
                continue
            entries = _parse_box_entries(line)
            if not entries:
                continue
            has_leading_space = line[:1].isspace()
            if len(entries) == 2:
                players.append({**entries[0], "team": left_team})
                players.append({**entries[1], "team": right_team})
            elif len(entries) == 1:
                players.append({**entries[0], "team": right_team if has_leading_space else left_team})

    # Defensive errors from the E: section.
    e_idx = next(
        (i for i, ln in enumerate(lines) if ln.strip().startswith("E:")),
        None,
    )
    error_text = ""
    if e_idx is not None:
        lob_idx = next(
            (i for i in range(e_idx, len(lines)) if "LOB:" in lines[i]),
            len(lines),
        )
        error_text = " ".join(lines[e_idx:lob_idx + 1]).split("LOB:", 1)[0]

    for p in players:
        p["errors"] = parse_error_count(error_text, p["player"])

    # Play-by-play derived stats.
    all_names = {p["player"] for p in players}
    pa, on_base, hit_score, total_bases = parse_play_by_play(block, all_names)
    for p in players:
        p["pa"] = pa[p["player"]]
        p["on_base"] = on_base[p["player"]]
        p["hit_score"] = hit_score[p["player"]]
        p["total_bases"] = total_bases[p["player"]]

    return {
        "game": game_num,
        "away": away,
        "home": home,
        "totals": {
            away: {"runs": away_r, "hits": away_h, "errors": away_e},
            home: {"runs": home_r, "hits": home_h, "errors": home_e},
        },
        "players": players,
        "error_text": error_text,
        "block": block,
    }


def parse_pdf(pdf_path):
    text = extract_text(pdf_path)
    games = [parse_game(block, num) for num, block in split_game_blocks(text)]
    return deduplicate(games), text


def parse_pdf_bytes(data):
    """Parse a PDF from raw bytes (used by the web app for uploads)."""
    from io import BytesIO
    reader = PdfReader(BytesIO(data))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    games = [parse_game(block, num) for num, block in split_game_blocks(text)]
    return deduplicate(games), text


def game_signature(game):
    players = tuple(sorted(
        (p["player"], p["ab"], p["runs"], p["hits"], p["rbi"]) for p in game["players"]
    ))
    totals = tuple(sorted(
        (team, t["runs"], t["hits"], t["errors"]) for team, t in game["totals"].items()
    ))
    return (game["away"], game["home"], totals, players)


def deduplicate(games):
    seen = set()
    unique = []
    for game in games:
        sig = game_signature(game)
        if sig in seen:
            continue
        seen.add(sig)
        unique.append(game)
    return unique


def detect_teams(games):
    teams = set()
    for game in games:
        teams.add(game["away"])
        teams.add(game["home"])
    return sorted(teams)


def compute_team_report(games, team):
    """Aggregate a team's games into the data structures used by the report."""
    team_games = [g for g in games if g["away"] == team or g["home"] == team]

    game_rows = []
    player_totals = defaultdict(Counter)
    player_game_rows = []

    for g in team_games:
        team_total = g["totals"].get(team, {})
        opponent = g["home"] if g["away"] == team else g["away"]
        opponent_total = g["totals"].get(opponent, {})
        game_rows.append({
            "game": g["game"],
            "matchup": f"{g['away']} at {g['home']}",
            "opponent": opponent,
            "result": "W" if team_total.get("runs", 0) > opponent_total.get("runs", 0) else "L",
            "team_runs": team_total.get("runs", 0),
            "team_hits": team_total.get("hits", 0),
            "team_errors": team_total.get("errors", 0),
            "opp_runs": opponent_total.get("runs", 0),
        })

        team_players = [p for p in g["players"] if p["team"] == team]
        for p in team_players:
            total = player_totals[p["player"]]
            for field in ("ab", "runs", "hits", "rbi", "errors", "pa", "on_base",
                          "hit_score", "total_bases"):
                total[field] += p[field]
            player_game_rows.append({
                "game": g["game"],
                "player": p["player"],
                "obp": p["on_base"] / p["pa"] if p["pa"] else 0,
                "hit_ratio": p["hit_score"] / p["pa"] / 100 if p["pa"] else 0,
                "total_bases": p["total_bases"],
                "slugging_average": p["total_bases"] / p["ab"] if p["ab"] else 0,
            })

    player_rows = []
    for player, total in sorted(player_totals.items()):
        ab, pa = total["ab"], total["pa"]
        player_rows.append({
            "player": player,
            "games": sum(
                1 for g in team_games
                if any(p["player"] == player and p["team"] == team for p in g["players"])
            ),
            "ab": ab,
            "runs": total["runs"],
            "hits": total["hits"],
            "rbi": total["rbi"],
            "errors": total["errors"],
            "pa": pa,
            "avg": round(total["hits"] / ab, 3) if ab else 0,
            "obp_proxy": round(total["on_base"] / pa, 3) if pa else 0,
            "hit_score": round(total["hit_score"] / pa, 1) if pa else 0,
            "total_bases": total["total_bases"],
            "slugging_average": round(total["total_bases"] / ab, 3) if ab else 0,
        })

    wins = sum(1 for row in game_rows if row["result"] == "W")

    # Improvement (first vs last appearance).
    improvement_rows = []
    for player in sorted({row["player"] for row in player_game_rows}):
        appearances = sorted(
            (row for row in player_game_rows if row["player"] == player),
            key=lambda row: row["game"],
        )
        first, last = appearances[0], appearances[-1]

        def improvement_percent(start, end):
            return round((end - start) / start * 100, 1) if start else None

        improvement_rows.append({
            "player": player,
            "first_game": first["game"],
            "last_game": last["game"],
            "obp_first": first["obp"],
            "obp_last": last["obp"],
            "obp_improvement": improvement_percent(first["obp"], last["obp"]),
            "hit_ratio_first": first["hit_ratio"],
            "hit_ratio_last": last["hit_ratio"],
            "hit_ratio_improvement": improvement_percent(first["hit_ratio"], last["hit_ratio"]),
        })

    # Defensive error analysis.
    error_player_rows = []
    error_game_rows = []
    error_position_totals = Counter()
    error_player_totals = Counter()
    error_events_by_game = Counter()

    for g in team_games:
        opponent = g["home"] if g["away"] == team else g["away"]
        team_players = [p for p in g["players"] if p["team"] == team]
        team_names = {p["player"] for p in team_players}
        positions = {p["player"]: p["pos"] for p in team_players}

        game_error_total = 0
        for p in team_players:
            count = p["errors"]
            if count:
                position = positions.get(p["player"], "Unknown")
                error_player_rows.append({
                    "game": g["game"], "opponent": opponent,
                    "player": p["player"], "position": position, "errors": count,
                })
                error_player_totals[p["player"]] += count
                error_position_totals[position] += count
                game_error_total += count
        error_game_rows.append({
            "game": g["game"], "opponent": opponent, "errors": game_error_total,
        })

        # Offensive error events (team batting innings containing an error event).
        names_sorted = sorted(team_names, key=len, reverse=True)
        inning = None
        for line in g["block"].splitlines():
            m = re.match(re.escape(team) + r" - (Top|Bottom) of the (\d+)(st|nd|rd|th):", line)
            if m:
                inning = f"{m.group(2)} ({m.group(1)})"
                continue
            if inning and re.match(r"\d+ runs?,", line.strip(), re.IGNORECASE):
                inning = None
                continue
            if not inning or "error" not in line.lower():
                continue
            player = next(
                (name for name in names_sorted if line.startswith(name + " ")),
                None,
            )
            event_match = re.search(
                r"(reached on error|advanced .*? on error|on error)", line, re.IGNORECASE
            )
            if player and event_match:
                error_events_by_game[g["game"]] += 1

    # Runs scored by opponent in innings containing an error.
    runs_after_error_rows = []
    for g in team_games:
        opponent = g["home"] if g["away"] == team else g["away"]
        current_inning = None
        error_in_inning = False
        for line in g["block"].splitlines():
            m = re.match(
                re.escape(opponent) + r" - (Top|Bottom) of the (\d+)(st|nd|rd|th):", line
            )
            if m:
                current_inning = f"{m.group(2)} ({m.group(1)})"
                error_in_inning = False
                continue
            run_match = re.match(r"(\d+) runs?,", line.strip(), re.IGNORECASE)
            if current_inning and run_match:
                if error_in_inning:
                    runs_after_error_rows.append({
                        "game": g["game"], "opponent": opponent,
                        "inning": current_inning, "runs": int(run_match.group(1)),
                    })
                current_inning = None
                error_in_inning = False
                continue
            if current_inning and "error" in line.lower():
                error_in_inning = True

    runs_after_error_totals = [
        {
            "game": row["game"],
            "opponent": row["opponent"],
            "runs": sum(item["runs"] for item in runs_after_error_rows
                        if item["game"] == row["game"]),
        }
        for row in error_game_rows
    ]

    game_numbers = sorted({row["game"] for row in game_rows})
    opponents_by_game = {row["game"]: row["opponent"] for row in game_rows}

    trend_by_player = defaultdict(dict)
    slugging_by_player = defaultdict(dict)
    for row in player_game_rows:
        trend_by_player[row["player"]][row["game"]] = row["obp"]
        slugging_by_player[row["player"]][row["game"]] = row["slugging_average"]

    return {
        "team": team,
        "game_rows": game_rows,
        "player_rows": player_rows,
        "player_game_rows": player_game_rows,
        "improvement_rows": improvement_rows,
        "error_player_rows": error_player_rows,
        "error_game_rows": error_game_rows,
        "error_position_totals": error_position_totals,
        "error_player_totals": error_player_totals,
        "error_events_by_game": error_events_by_game,
        "runs_after_error_rows": runs_after_error_rows,
        "runs_after_error_totals": runs_after_error_totals,
        "game_numbers": game_numbers,
        "opponents_by_game": opponents_by_game,
        "trend_by_player": trend_by_player,
        "slugging_by_player": slugging_by_player,
        "wins": wins,
        "total_runs": sum(row["team_runs"] for row in game_rows),
        "total_hits": sum(row["team_hits"] for row in game_rows),
        "player_count": len(player_rows),
        "game_count": len(game_rows),
    }

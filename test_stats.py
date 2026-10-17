"""Self-check: parse the bundled PDF and verify the new stat columns."""
from parser import parse_pdf, compute_team_report

games, _ = parse_pdf("REPORT PERTANDINGAN.pdf")
assert games, "no games parsed"

report = compute_team_report(games, "RUSA HITAM")
rows = {r["player"]: r for r in report["player_rows"]}

# ARNAV FAZIAN: game 1 box = 3 AB, 2 H; play-by-play has a triple + a solo HR.
arnav = rows["ARNAV FAZIAN"]
assert arnav["ab"] >= 3
assert arnav["hr"] >= 1, arnav
assert arnav["triples"] >= 1, arnav
assert arnav["b1"] == arnav["hits"] - arnav["doubles"] - arnav["triples"] - arnav["hr"]

# GYLFI LEV YASHIN pitched 3.00 IP / 10 ER in one game (pitching block).
gylfi = rows["GYLFI LEV YASHIN"]
assert gylfi["ip"] >= 3.0 and gylfi["er"] >= 10, gylfi

# Every requested field exists and is a non-negative number.
for r in rows.values():
    for f in ("pa", "ab", "b1", "doubles", "triples", "hr", "runs", "rbi",
              "bb", "k", "hbp", "sf", "pitches", "ip", "er"):
        assert isinstance(r[f], (int, float)) and r[f] >= 0, (r["player"], f, r[f])
    assert r["pitches"] == 0  # not present in this PDF

# KUMARA ALDEBARAN (LABS) has a "sacrifice flied, 1 RBI" in the PDF.
labs = {r["player"]: r for r in compute_team_report(games, "LABS")["player_rows"]}
assert labs["KUMARA ALDEBARAN"]["sf"] >= 1, labs["KUMARA ALDEBARAN"]

# ARNAV scored at least 2 runs in game 1 (box score).
assert arnav["runs"] >= 2, arnav

print(f"OK: {len(games)} games, {len(rows)} RUSA HITAM players, new columns verified")

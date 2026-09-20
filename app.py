"""Flask web app for parsing baseball "REPORT PERTANDINGAN" PDFs into statistics.

Endpoints:
    GET  /          -> upload page
    POST /parse     -> upload a PDF, returns detected teams + a session token
    POST /report    -> given token + team, returns the rendered report HTML
"""

import os
import uuid

from flask import Flask, jsonify, render_template, request

from parser import compute_team_report, detect_teams, parse_pdf_bytes
from render import render_report

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32 MB upload cap

# token -> {"games": [...], "filename": str}
_SESSIONS = {}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/parse", methods=["POST"])
def parse():
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify({"error": "Tidak ada file yang diunggah."}), 400

    data = uploaded.read()
    if not data:
        return jsonify({"error": "File kosong."}), 400

    try:
        games, _text = parse_pdf_bytes(data)
    except Exception as exc:  # noqa: BLE001 - surface a friendly message
        return jsonify({"error": f"Gagal membaca PDF: {exc}"}), 400

    if not games:
        return jsonify({"error": "Tidak ada pertandingan yang ditemukan di PDF."}), 400

    teams = detect_teams(games)
    if not teams:
        return jsonify({"error": "Tidak ada tim yang terdeteksi."}), 400

    token = uuid.uuid4().hex
    _SESSIONS[token] = {"games": games, "filename": uploaded.filename}

    return jsonify({
        "token": token,
        "teams": teams,
        "game_count": len(games),
        "filename": uploaded.filename,
    })


@app.route("/report", methods=["POST"])
def report():
    payload = request.get_json(silent=True) or {}
    token = payload.get("token")
    team = payload.get("team")

    session = _SESSIONS.get(token)
    if session is None:
        return jsonify({"error": "Sesi berakhir atau tidak valid. Silakan unggah ulang PDF."}), 404

    teams = detect_teams(session["games"])
    if not team or team not in teams:
        return jsonify({"error": "Tim tidak valid.", "teams": teams}), 400

    report_data = compute_team_report(session["games"], team)
    html = render_report(report_data, session["filename"])

    return jsonify({
        "html": html,
        "team": team,
        "filename": session["filename"],
    })


if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "1") == "1",
    )

"""
flask web server for the athlete wellness dashboard.
serves the frontend and provides api endpoints for pipeline data.
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, send_from_directory


app = Flask(
    __name__,
    static_folder="frontend/static",
    static_url_path="/static",
)


def load_output(filename):
    """loads a file from the outputs directory."""
    path = os.path.join(os.path.dirname(__file__), "outputs", filename)
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        if filename.endswith(".json"):
            return json.load(f)
        return f.read()


@app.route("/")
def index():
    """serves the main dashboard."""
    return send_from_directory("frontend", "index.html")


@app.route("/api/master")
def api_master():
    """returns the master output json."""
    data = load_output("master_output.json")
    if data is None:
        return jsonify({"error": "pipeline has not been run yet"}), 404
    return jsonify(data)


@app.route("/api/recommendations")
def api_recommendations():
    """returns the ai recommendations text."""
    text = load_output("recommendations.txt")
    if text is None:
        return jsonify({"error": "no recommendations generated yet"}), 404
    return jsonify({"recommendations": text})


if __name__ == "__main__":
    app.run(debug=True, port=5050)

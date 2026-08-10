from __future__ import annotations

import logging
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from gearbox_spectra.service import build_phase1_result, build_phase2_result
from gearbox_spectra.uff import UFFError


ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
DEFECT_TABLE = ROOT / "defect frequency calculation.pdf"

app = Flask(__name__, static_folder=str(FRONTEND), static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vibration-analysis")


@app.get("/")
def index():
    return send_from_directory(FRONTEND, "index.html")


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "vibration-analysis"})


def _uploaded_file():
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        raise UFFError("Choose a .uff file before analyzing.")
    return upload.filename, upload.read()


@app.post("/api/analyze")
def analyze():
    try:
        filename, raw = _uploaded_file()
        return jsonify(build_phase1_result(raw, filename))
    except (UFFError, ValueError, OSError) as exc:
        return jsonify({"error": str(exc)}), 422
    except Exception:
        logger.exception("Unexpected Phase 1 analysis failure")
        return jsonify({"error": "Unable to process the UFF file."}), 500


@app.post("/api/analyze/phase2")
def analyze_phase2():
    try:
        filename, raw = _uploaded_file()
        sidebands = request.form.get("sideband_analysis", "false").lower() == "true"
        result = build_phase2_result(raw, filename, DEFECT_TABLE, sideband_analysis=sidebands)
        return jsonify(result)
    except (UFFError, ValueError, OSError) as exc:
        return jsonify({"error": str(exc)}), 422
    except Exception:
        logger.exception("Unexpected Phase 2 analysis failure")
        return jsonify({"error": "Unable to complete the requested analysis."}), 500


@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": "The UFF file is too large. Maximum size is 64 MB."}), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)

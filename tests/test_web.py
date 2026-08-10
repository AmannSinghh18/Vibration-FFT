from __future__ import annotations

from io import BytesIO
from pathlib import Path
import unittest

from app import app


ROOT = Path(__file__).resolve().parents[1]
UFF_FILE = ROOT / "UFF Files Bearing defect" / "timesignal (2).uff"


class WebApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = app.test_client()

    def test_health_and_frontend_routes(self) -> None:
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Vibration Analysis", page.data)
        page.close()

    def test_phase1_accepts_real_uff(self) -> None:
        response = self.client.post(
            "/api/analyze",
            data={"file": (UFF_FILE.open("rb"), UFF_FILE.name)},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["phase"], 1)
        self.assertEqual(len(payload["spectrum"]["frequencies"]), 16385)
        self.assertEqual(payload["metadata"]["reference"]["reference_image"], "Uff(2).jpg")

    def test_invalid_extension_is_rejected(self) -> None:
        response = self.client.post(
            "/api/analyze",
            data={"file": (BytesIO(b"not a UFF"), "signal.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn(".uff", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()

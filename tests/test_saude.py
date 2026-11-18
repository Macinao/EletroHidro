from fastapi.testclient import TestClient

from app.main import app


def test_saude() -> None:
    resposta = TestClient(app).get("/saude")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}

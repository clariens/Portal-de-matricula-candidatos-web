"""App do teste e2e (Playwright): o BFF real com o dublê do Lyceum (tests/fake_lyceum.py). Nunca usar fora dos testes."""

from app.main import app
from tests.fake_lyceum import FakeLyceum

app.state.gateway_factory = lambda settings, client: FakeLyceum()

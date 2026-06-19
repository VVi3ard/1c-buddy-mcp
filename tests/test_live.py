import os

import pytest

from onec_buddy_mcp.client import OneCAIClient
from onec_buddy_mcp.config import Settings
from onec_buddy_mcp.service import OneCToolService


pytestmark = pytest.mark.live


@pytest.mark.asyncio
async def test_live_general_question() -> None:
    if os.environ.get("RUN_LIVE_TESTS") != "1":
        pytest.skip("set RUN_LIVE_TESTS=1 to call the real 1C.ai API")
    if not os.environ.get("ONEC_AI_TOKEN"):
        pytest.skip("ONEC_AI_TOKEN is not available")

    settings = Settings()
    async with OneCAIClient(settings) as client:
        service = OneCToolService(client)
        answer = await service.ask_1c_ai("Ответь одним словом: тест")

    assert answer.strip()
    assert settings.ONEC_AI_TOKEN.get_secret_value() not in answer

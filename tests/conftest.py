import os
import pytest

@pytest.fixture(autouse=True)
def set_dummy_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

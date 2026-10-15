"""The model layer: provider choice and reading JSON out of a model's reply. No key, no network."""

import pytest

from aiquality.models import extract_json, get_chat_model


def test_json_is_read_from_fenced_or_chatty_replies():
    assert extract_json('```json\n{"verdict": "PASS"}\n```') == {"verdict": "PASS"}
    assert extract_json('Here you go: {"verdict": "FAIL", "reason": "x"} hope that helps') == \
        {"verdict": "FAIL", "reason": "x"}


def test_an_unknown_provider_says_where_to_add_one():
    with pytest.raises(ValueError, match="aiquality/models/chat_model.py"):
        get_chat_model("any-model", provider="nowhere")


def test_importing_the_package_loads_no_provider_library():
    import subprocess
    import sys
    code = "import sys, aiquality, aiquality.models; print('anthropic' in sys.modules)"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "False"

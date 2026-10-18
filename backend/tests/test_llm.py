"""Groq extraction engine: request shape, strict schema, rate-limit handling. No network."""

import json

import httpx
import pytest

from app.config import Settings
from app.errors import ApiError
from app.services import llm

JD_OUTPUT = {
    "title": "Data Engineer",
    "requirements": [{"skill": "python", "kind": "required", "min_level": 2, "quote": "Strong Python"}],
    "red_flags": [],
}


def ok(content: dict, tokens: int = 900) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(content)}}],
              "usage": {"total_tokens": tokens}},
        headers={"x-ratelimit-remaining-tokens": "7000"},
    )


def too_many(retry_after: str) -> httpx.Response:
    return httpx.Response(429, json={"error": {"message": "rate limited"}}, headers={"retry-after": retry_after})


@pytest.fixture
def groq(monkeypatch):
    """Route Groq calls to a scripted handler; fresh budgets and settings for every test."""
    calls: list[dict] = []
    script: list = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        step = script.pop(0)
        return step(body) if callable(step) else step

    settings = Settings(groq_api_key="gsk_test", groq_model="primary", groq_fallback_model="fallback",
                        groq_rpm=30, groq_tpm=7500)
    monkeypatch.setattr(llm, "get_settings", lambda: settings)
    monkeypatch.setattr(llm, "_http", lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(llm, "_budgets", {})
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    return calls, script, settings


def test_request_uses_strict_schema_and_low_reasoning(groq):
    calls, script, _ = groq
    script.append(ok(JD_OUTPUT))
    result = llm.extract_job_description("We need Strong Python.")
    assert result.requirements[0].skill == "python"
    body = calls[0]
    assert body["model"] == "primary" and body["temperature"] == 0
    assert body["reasoning_effort"] == "low" and body["include_reasoning"] is False
    schema = body["response_format"]["json_schema"]
    assert schema["strict"] is True
    # Strict mode: every property required, no extra properties, at every level.
    assert set(schema["schema"]["required"]) == {"title", "requirements", "red_flags"}
    assert set(schema["schema"]["properties"]) == {"title", "requirements", "red_flags"}  # the "title" field survives
    assert schema["schema"]["properties"]["title"] == {"anyOf": [{"type": "string"}, {"type": "null"}]}
    assert schema["schema"]["additionalProperties"] is False
    item = schema["schema"]["$defs"]["ExtractedRequirement"]
    assert item["additionalProperties"] is False and set(item["required"]) == {"skill", "kind", "min_level", "quote"}
    assert "<job_description>" in body["messages"][1]["content"]


def test_short_retry_after_is_retried_on_same_model(groq):
    calls, script, _ = groq
    script.extend([too_many("2"), ok(JD_OUTPUT)])
    llm.extract_job_description("We need Strong Python.")
    assert [c["model"] for c in calls] == ["primary", "primary"]


def test_long_retry_after_moves_to_fallback_model(groq):
    calls, script, _ = groq
    script.extend([too_many("45"), ok(JD_OUTPUT)])
    llm.extract_job_description("We need Strong Python.")
    assert [c["model"] for c in calls] == ["primary", "fallback"]


def test_both_models_busy_fails_fast_with_wait_time(groq):
    calls, script, _ = groq
    script.extend([too_many("45"), too_many("20")])
    with pytest.raises(ApiError) as caught:
        llm.extract_job_description("We need Strong Python.")
    assert caught.value.status_code == 503 and "about 20 seconds" in caught.value.detail
    # The cooldown is remembered: the next call does not hit Groq at all.
    with pytest.raises(ApiError):
        llm.extract_job_description("We need Strong Python.")
    assert len(calls) == 2


def test_local_token_budget_stops_calls_before_groq_does(groq):
    calls, script, settings = groq
    settings.groq_tpm = 4000  # one call's estimate (~2,000 output + input) uses most of it
    script.append(ok(JD_OUTPUT, tokens=3900))
    llm.extract_job_description("We need Strong Python.")
    with pytest.raises(ApiError) as caught:  # both models: primary over budget, fallback has its own budget
        settings.groq_fallback_model = ""
        llm.extract_job_description("We need Strong Python.")
    assert "busy" in caught.value.detail and len(calls) == 1


def test_truncated_output_is_a_clear_error(groq):
    _, script, _ = groq
    script.append(httpx.Response(200, json={"choices": [{"finish_reason": "length", "message": {"content": "{"}}],
                                            "usage": {"total_tokens": 10}}))
    with pytest.raises(ApiError) as caught:
        llm.extract_job_description("x")
    assert caught.value.status_code == 422


def test_no_key_means_switched_off(monkeypatch):
    monkeypatch.setattr(llm, "get_settings", lambda: Settings(groq_api_key=""))
    with pytest.raises(ApiError) as caught:
        llm.extract_resume("Python developer")
    assert caught.value.status_code == 503 and "switched off" in caught.value.detail


@pytest.mark.parametrize(("value", "seconds"), [("2", 2), ("1.5s", 1.5), ("2m59.5s", 179.5), ("120ms", 0.12)])
def test_duration_parsing(value, seconds):
    assert llm._seconds(value) == pytest.approx(seconds)


def test_inputs_are_trimmed_to_budget(groq):
    calls, script, _ = groq
    script.append(ok({"skills": []}))
    llm.extract_resume("x" * 50000)
    assert len(calls[0]["messages"][1]["content"]) < llm.MAX_RESUME_CHARS + 50


def test_longest_resume_fits_one_tpm_window(groq):
    """Input + output budget of a maximum-length resume must fit Groq's 7,500 TPM, or it could never run."""
    calls, script, settings = groq
    script.append(ok({"skills": []}))
    llm.extract_resume("x" * 50000)
    assert calls[0]["max_completion_tokens"] == llm.MAX_RESUME_OUTPUT_TOKENS
    assert llm._estimate_tokens(calls[0]["messages"], llm.MAX_RESUME_OUTPUT_TOKENS) <= settings.groq_tpm


def test_schema_violation_moves_to_fallback_model(groq):
    calls, script, _ = groq
    bad = httpx.Response(400, json={"error": {"code": "json_validate_failed", "message": "does not match"}})
    script.extend([bad, ok(JD_OUTPUT)])
    assert llm.extract_job_description("We need Strong Python.").requirements
    assert [c["model"] for c in calls] == ["primary", "fallback"]


def test_schema_violation_on_both_models_is_a_retry_message(groq):
    _, script, _ = groq
    bad = httpx.Response(400, json={"error": {"code": "json_validate_failed", "message": "does not match"}})
    script.extend([bad, bad])
    with pytest.raises(ApiError) as caught:
        llm.extract_job_description("We need Strong Python.")
    assert caught.value.status_code == 503 and "try again" in caught.value.detail

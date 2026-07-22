"""
Unit tests for dags/utils/alerting.py's notify_failure callback.
Run with: pytest tests/test_alerting.py

These mock requests.post so they don't depend on a real Ollama instance
being reachable — notify_failure's two code paths (successful LLM call,
and the fallback when Ollama is unreachable/slow) are each exercised
directly, since a manual `airflow tasks test` run can only ever hit
whichever path Ollama's current state happens to produce.
"""

from unittest.mock import MagicMock, patch

from dags.utils.alerting import notify_failure


def _make_context(exception="boom"):
    task_instance = MagicMock()
    task_instance.task_id = "some_task"
    dag = MagicMock()
    dag.dag_id = "some_dag"
    return {"task_instance": task_instance, "dag": dag, "exception": exception}


def test_notify_failure_prints_llm_summary_on_success(capsys):
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "The table was missing."}

    with patch(
        "dags.utils.alerting.requests.post", return_value=mock_response
    ) as mock_post:
        notify_failure(_make_context(exception="relation does not exist"))

    args, kwargs = mock_post.call_args
    assert "relation does not exist" in kwargs["json"]["prompt"]
    assert "some_dag" in kwargs["json"]["prompt"]
    assert "some_task" in kwargs["json"]["prompt"]

    out = capsys.readouterr().out
    assert "FAILURE ALERT" in out
    assert "some_dag" in out
    assert "some_task" in out
    assert "The table was missing." in out


def test_notify_failure_falls_back_when_ollama_unreachable(capsys):
    with patch(
        "dags.utils.alerting.requests.post", side_effect=ConnectionError("refused")
    ):
        notify_failure(_make_context())

    out = capsys.readouterr().out
    assert "FAILURE ALERT" in out
    assert "Alert summary generation failed" in out
    assert "refused" in out


def test_notify_failure_falls_back_on_malformed_response(capsys):
    mock_response = MagicMock()
    mock_response.json.return_value = {"unexpected": "shape"}

    with patch("dags.utils.alerting.requests.post", return_value=mock_response):
        notify_failure(_make_context())

    out = capsys.readouterr().out
    assert "FAILURE ALERT" in out
    assert "No summary available" in out

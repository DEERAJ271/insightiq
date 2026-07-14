"""
DAG integrity tests — verify all DAGs load without errors and follow
basic structural conventions. Run with: pytest tests/test_dag_integrity.py

These don't test business logic (that's what nl2sql-test etc. do for the
main project); they test that Airflow can actually parse and load every
DAG file without blowing up, which is a surprisingly common CI check in
real Airflow projects.
"""
import os
import pytest
from airflow.models import DagBag
from dags.utils.alerting import notify_failure


@pytest.fixture(scope="module")
def dagbag():
    return DagBag(dag_folder="dags/")


def test_no_import_errors(dagbag):
    assert len(dagbag.import_errors) == 0, (
        f"DAG import failures found: {dagbag.import_errors}"
    )


def test_expected_dags_present(dagbag):
    expected_dag_ids = {
        "hello_world",
        "insightiq_data_validation",
        "insightiq_category_summary",
        "insightiq_category_deep_dive",
    }
    actual_dag_ids = set(dagbag.dags.keys())
    missing = expected_dag_ids - actual_dag_ids
    assert not missing, f"Expected DAGs not found: {missing}"


def test_dags_have_tags(dagbag):
    for dag_id, dag in dagbag.dags.items():
        if dag_id == "hello_world":
            continue  # test DAG, exempt
        assert dag.tags, f"DAG {dag_id} has no tags set"


def test_dags_have_owner_or_default_args(dagbag):
    for dag_id, dag in dagbag.dags.items():
        assert dag.default_args is not None or dag.owner, (
            f"DAG {dag_id} has neither default_args nor an explicit owner"
        )


def test_no_cycles(dagbag):
    # DagBag.process_file already raises on cycles during load, but this
    # makes the check explicit and gives a clearer failure message.
    for dag_id, dag in dagbag.dags.items():
        try:
            dag.topological_sort()
        except Exception as e:
            pytest.fail(f"DAG {dag_id} has a cycle or invalid structure: {e}")


def test_failure_alerting_wired(dagbag):
    dags_expecting_alerting = {
        "insightiq_data_validation",
        "insightiq_category_deep_dive",
    }
    for dag_id in dags_expecting_alerting:
        dag = dagbag.dags.get(dag_id)
        assert dag is not None, f"DAG {dag_id} not found"
        callback = (dag.default_args or {}).get("on_failure_callback")
        assert callback is notify_failure, (
            f"DAG {dag_id} does not have notify_failure wired as its "
            f"on_failure_callback (found: {callback!r})"
        )


def test_validation_dag_has_expected_tasks(dagbag):
    dag = dagbag.dags.get("insightiq_data_validation")
    assert dag is not None
    task_ids = {t.task_id for t in dag.tasks}
    expected = {
        "check_null_foreign_keys",
        "check_duplicate_orders",
        "check_review_score_range",
        "check_freight_outliers",
    }
    assert expected.issubset(task_ids), f"Missing tasks: {expected - task_ids}"


def test_ge_validation_dag_present_and_loads(dagbag):
    assert "insightiq_ge_validation" in dagbag.dags, (
        "insightiq_ge_validation DAG not found"
    )
    assert "insightiq_ge_validation" not in dagbag.import_errors, (
        f"insightiq_ge_validation failed to import: "
        f"{dagbag.import_errors.get('insightiq_ge_validation')}"
    )

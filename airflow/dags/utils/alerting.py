import requests

def notify_failure(context):
    task_id = context["task_instance"].task_id
    dag_id = context["dag"].dag_id
    exception = context.get("exception", "Unknown error")

    prompt = (
        f"An Airflow task failed. DAG: {dag_id}, Task: {task_id}, "
        f"Error: {exception}. Write a 1-2 sentence alert summary for "
        f"an on-call engineer explaining what likely went wrong."
    )

    try:
        response = requests.post(
            "http://host.docker.internal:11434/api/generate",
            json={"model": "llama3.2", "prompt": prompt, "stream": False},
            timeout=15,
        )
        summary = response.json().get("response", "No summary available")
    except Exception as e:
        summary = f"(Alert summary generation failed: {e})"

    print(f"=== FAILURE ALERT ===\nDAG: {dag_id}\nTask: {task_id}\n{summary}\n=====================")

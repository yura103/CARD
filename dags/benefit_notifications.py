"""Optional Airflow 3 DAG. Put repository on PYTHONPATH in the Airflow worker."""
import pendulum
from airflow.sdk import dag, task


@dag(schedule="0 8 * * *", start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Seoul"),
     catchup=False, tags=["cardbenepick", "demo"])
def benefit_notifications():
    @task
    def prepare_preview():
        from app.notifications import build_notification_preview
        return build_notification_preview()
    prepare_preview()


benefit_notifications()

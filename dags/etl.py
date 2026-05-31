"""
Airflow DAG to orchestrate ETL pipeline
"""

import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}

with DAG(
    dag_id="zyra_etl_task",
    default_args=default_args,
    description="university etl pipeline for zyra",
    schedule_interval="@daily",
    start_date=datetime(2026, 5, 24),
    catchup=False,
    tags=["zyra", "etl"],
) as dag:

    # Task 1: 
    ingest_raw_data = PythonOperator(
        task_id='ingest_raw_data',
        python_callable=ingest_retail_data
    )

    """# Task 2:
    fetch_rates = PythonOperator(
        task_id='fetch_rates',
        python_callable=fetch_and_upload_rates,
        op_kwargs={'start_date': '2009-01-01', 'end_date': '2011-12-31'}
    )"""

    # Task Dependencies
    
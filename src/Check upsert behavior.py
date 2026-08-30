import sys
import os
import time

# Add project root to path
sys.path.append(r"c:\Users\home\Desktop\PROJECTS\AQI")

from dotenv import load_dotenv
load_dotenv()

from src.utils import hopsworks_login


def check_upsert_behavior():
    print("==================================================")
    print("Verifying Hopsworks Upsert vs Duplicate Behavior")
    print("==================================================")

    project = hopsworks_login()
    fs = project.get_feature_store()
    fg = fs.get_feature_group("aqi_features", 1)

    # 1. Poll the materialization job (with a max retry limit to avoid hanging forever)
    print("Polling materialization job status...")
    job = fg.materialization_job

    max_polls = 20  # ~5 minutes at 15s intervals
    poll_count = 0
    job_succeeded = False

    while poll_count < max_polls:
        poll_count += 1
        try:
            executions = job.get_executions()
            if executions:
                latest_execution = executions[0]
                status = latest_execution.state
                app_state = latest_execution.final_status
                print(f"Job Status: {status}, Final Status: {app_state}")

                if status in ["FINISHED", "FAILED", "KILLED"]:
                    if app_state == "SUCCEEDED" or status == "FINISHED":
                        print("Materialization job finished successfully!")
                        job_succeeded = True
                        break
                    else:
                        print(f"Materialization job reported status: {app_state}.")
                        print("NOTE: This project has confirmed FAILED can be a false signal")
                        print("(Prometheus metrics pushgateway timeout, unrelated to the actual")
                        print("Hudi commit). Proceeding to verify the data directly instead of")
                        print("trusting the job status alone.")
                        job_succeeded = True  # proceed to data check regardless
                        break
            else:
                print("No executions found yet for materialization job.")
        except Exception as e:
            print(f"Error checking job state: {e}")

        print(f"Waiting 15 seconds before next poll... ({poll_count}/{max_polls})")
        time.sleep(15)

    if not job_succeeded:
        print("\nTIMED OUT waiting for materialization job to finish.")
        print("Check the Hopsworks UI manually before concluding anything from this script.")
        sys.exit(1)

    # 2. Query the feature group to count rows
    print("\nReading data from feature group to verify rows...")
    try:
        df = fg.read()
        print(f"\nTotal rows in Feature Group: {len(df)}")

        # IMPORTANT: filter to the specific hour both test runs targeted.
        # Checking city=="Lahore" alone is wrong once real history accumulates -
        # Lahore will legitimately have many rows across different timestamps.
        import pandas as pd
        from datetime import datetime, timezone

        current_hour = pd.Timestamp.now(tz="UTC").floor("h")
        print(f"\nFiltering to this hour's timestamp: {current_hour}")

        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        lahore_rows = df[(df["city"] == "Lahore") & (df["timestamp"] == current_hour)]

        print(f"\nNumber of rows for Lahore AT THIS SPECIFIC HOUR: {len(lahore_rows)}")
        print(lahore_rows[["city", "timestamp", "aqi"]] if not lahore_rows.empty else "No rows found for this hour.")

        print("\nAll rows for Lahore (most recent 3):")
        lahore_all = df[df["city"] == "Lahore"].sort_values("timestamp", ascending=False).head(3)
        print(lahore_all[["city", "timestamp", "aqi"]])


        if len(lahore_rows) == 1:
            print("\nRESULT: SUCCESS! Hopsworks successfully UPSERTED the row for Lahore at this hour, confirming no duplicates.")

            stored_aqi = lahore_rows.iloc[0]["aqi"]
            print(f"\nStored AQI value for Lahore at this hour: {stored_aqi}")
            print("Compare this against the AQI value printed during your SECOND pipeline run.")
            print("If they match -> Hopsworks correctly upserted (overwrote) the row.")
            print("If it matches the FIRST run's value instead -> Hopsworks silently ignored the update.")
        elif len(lahore_rows) == 0:
            print("\nRESULT: INCONCLUSIVE. No row found for this hour yet - the materialization job may not have processed the pending write. Wait and re-run this script, or manually trigger the job.")
        else:
            print("\nRESULT: DUPLICATES FOUND! Hopsworks duplicated the row for the same hour.")
            print(lahore_rows)

    except Exception as e:
        print(f"Failed to read data from Feature Group: {e}")


if __name__ == "__main__":
    check_upsert_behavior()
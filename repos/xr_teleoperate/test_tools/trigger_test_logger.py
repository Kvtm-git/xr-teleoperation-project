import csv
import os
import time
import numpy as np


class TriggerTestLogger:
    def __init__(self, output_dir="test_logs/trigger_mapping", test_name="trigger_test"):
        os.makedirs(output_dir, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.file_path = os.path.join(output_dir, f"{test_name}_{timestamp}.csv")

        self.start_time = time.time()
        self.rows = []

    def log(self, left_trigger, right_trigger, left_q_target, right_q_target):
        now = time.time()
        time_s = now - self.start_time

        left_q_target = np.array(left_q_target).flatten()
        right_q_target = np.array(right_q_target).flatten()

        row = {
            "time_s": time_s,
            "left_trigger": float(left_trigger),
            "right_trigger": float(right_trigger),
        }

        for i, value in enumerate(left_q_target):
            row[f"left_joint_{i}"] = float(value)

        for i, value in enumerate(right_q_target):
            row[f"right_joint_{i}"] = float(value)

        self.rows.append(row)

    def save(self):
        if not self.rows:
            print("Ingen trigger-testdata blev gemt.")
            return

        fieldnames = list(self.rows[0].keys())

        with open(self.file_path, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.rows)

        print(f"Trigger-testdata gemt i: {self.file_path}")
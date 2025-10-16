# ai_model.py
import pandas as pd

def classify_from_csv(csv_file):
    """
    Reads the latest row from imu_data.csv and predicts a movement class.
    """
    try:
        df = pd.read_csv(csv_file)
        if df.empty:
            return -1  # no data yet
        last_row = df.iloc[-1].values  # numpy array
        # --- Replace this with real AI logic ---
        movement_class = int(sum(last_row) % 4)  # dummy logic
        return movement_class
    except Exception as e:
        print(f"AI model error: {e}")
        return -1


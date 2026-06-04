import pandas as pd
import numpy as np

INPUT_FILE = "imu_training_data_v2.csv"
OUTPUT_FILE = "imu_labeled.csv"

# ================= CALIBRATION =================

INACTIVITY_RANGE_THRESHOLD = 6.0
WINDOW_SIZE = 40

COMBINED_ACCEL_THRESH = 60.0    # fall rotation scenario
COMBINED_GYRO_THRESH = 200.0

MASSIVE_IMPACT_THRESH = 92.0    # straight slam fall scenario

# =====================================================

def magnitude(x, y, z):
    return np.sqrt(x*x + y*y + z*z)

def get_window_range(df, idx, window):
    start = max(0, idx - window)

    ax = df["ax"].iloc[start:idx+1].to_numpy()
    ay = df["ay"].iloc[start:idx+1].to_numpy()
    az = df["az"].iloc[start:idx+1].to_numpy()

    # FIXED: correct magnitude calc
    mags = np.sqrt(ax*ax + ay*ay + az*az)

    return np.ptp(mags)  # range (max - min)

def label_row(df, idx):
    ax, ay, az = df.loc[idx, ["ax", "ay", "az"]]
    gx, gy, gz = df.loc[idx, ["gx", "gy", "gz"]]

    acc_mag = magnitude(ax, ay, az)
    gyro_mag = magnitude(gx, gy, gz)

    # ------------------ FALL DETECTION --------------------

    # Scenario A: Rotational Tumble
    if (acc_mag > COMBINED_ACCEL_THRESH) and (gyro_mag > COMBINED_GYRO_THRESH):
        return "fall"

    # Scenario B: Massive vertical impact
    if acc_mag > MASSIVE_IMPACT_THRESH:
        return "fall"

    # ------------------ INACTIVITY ------------------------

    dyn_range = get_window_range(df, idx, WINDOW_SIZE)
    if dyn_range < INACTIVITY_RANGE_THRESHOLD:
        return "inactivity"

    # ------------------ DEFAULT ---------------------------
    return "walking"


# ===================== PROCESS =====================

print(f"📂 Reading {INPUT_FILE}...")
df = pd.read_csv(INPUT_FILE)

labels = []
total_len = len(df)

print(f"   Processing {total_len} rows...")

for i in range(total_len):
    labels.append(label_row(df, i))
    if i % 5000 == 0:
        print(f"   Progress: {i}/{total_len} ({round(i/total_len*100)}%)", end='\r')

df["label"] = labels
df.to_csv(OUTPUT_FILE, index=False)

count_fall = df['label'].value_counts().get('fall', 0)

print(f"\n✔ Done. Labels breakdown:")
print(df['label'].value_counts())
print("-" * 40)
print(f"🎯 Detected Falls: {count_fall}")

if 100 <= count_fall <= 2000:
    print("   ✅ SUCCESS: Fall events detected within expected range.")
elif count_fall > 2000:
    print("   ⚠️ High fall count. Accel threshold (60) may be too low.")
else:
    print("   ⚠️ Low fall count. Thresholds may be too strict.")
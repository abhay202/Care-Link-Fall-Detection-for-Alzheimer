import pandas as pd
import numpy as np
import joblib
import os
import sys
from sklearn.model_selection import train_test_split
from tslearn.preprocessing import TimeSeriesScalerMinMax
from tslearn.neighbors import KNeighborsTimeSeriesClassifier

WINDOW_SIZE = 150
STEP_SIZE = 10

FILENAME = "imu_labeled.csv"
MODEL_NAME = "fast_model_v1.pkl"
SCALER_NAME = "fast_scaler_v1.pkl"

SENSOR_COLS = [
    'ax', 'ay', 'az',
    'gx', 'gy', 'gz',
    'sound_level'
]

ALLOWED_LABELS = ['fall', 'walking', 'inactivity']

print(f"Loading data from {FILENAME}...")
if not os.path.exists(FILENAME):
    print(f"❌ Error: '{FILENAME}' not found.")
    sys.exit(1)

df = pd.read_csv(FILENAME)
df = df.dropna()
print(f"Filtering dataset to keep only: {ALLOWED_LABELS}...")
df = df[df['label'].isin(ALLOWED_LABELS)]

max_accel = df[['ax', 'ay', 'az']].max().max()
if max_accel < 9.0:
    print("\n⚠️  WARNING: Max acceleration < 1g. Ensure 8g scaling was used in collector.")

def create_windows(df):
    X, y = [], []
    for start in range(0, len(df) - WINDOW_SIZE, STEP_SIZE):
        end = start + WINDOW_SIZE
        if end > len(df):
            break
        window_df = df.iloc[start:end]
        try:
            label_counts = window_df['label'].value_counts()
            most_common_label = label_counts.idxmax()
            if 'fall' in label_counts:
                if label_counts['fall'] > (WINDOW_SIZE * 0.3):
                    most_common_label = 'fall'
            ts_window = window_df[SENSOR_COLS].values
            X.append(ts_window)
            y.append(most_common_label)
        except Exception:
            continue
    return np.array(X), np.array(y)

print(f"Segmenting entire dataset (Size: {WINDOW_SIZE}, Step: {STEP_SIZE})...")
X, y = create_windows(df)

print(f"✅ Created {len(X)} windows.")
unique, counts = np.unique(y, return_counts=True)
print("   Class Distribution:")
for label, count in zip(unique, counts):
    print(f"   • {label}: {count} windows")

if len(X) == 0:
    print("❌ Error: No windows created.")
    sys.exit(1)

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

print("-" * 50)
print(f"🚀 TRAINING ON ENTIRE DATASET (No Balancing)")
print(f"   Training Samples: {len(X_train)}")
print(f"   Testing Samples:  {len(X_test)}")
print("-" * 50)

print("Scaling time-series data...")
scaler = TimeSeriesScalerMinMax()
X_train = scaler.fit_transform(X_train)
X_test = scaler.transform(X_test)

print("Training KNN-DTW model (Radius=10)...")
clf = KNeighborsTimeSeriesClassifier(
    n_neighbors=3,
    metric='dtw',
    metric_params={'global_constraint': 'sakoe_chiba', 'sakoe_chiba_radius': 10},
    n_jobs=1
)

clf.fit(X_train, y_train)

score = clf.score(X_test, y_test)
print(f"\n🎉 Model Accuracy on Test Set: {score*100:.2f}%")

joblib.dump(clf, MODEL_NAME)
joblib.dump(scaler, SCALER_NAME)

print(f"✅ SAVED: {MODEL_NAME} and {SCALER_NAME}")

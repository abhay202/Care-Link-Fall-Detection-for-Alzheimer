# Subsystem Overview

This project contains three main components:
- Subsystem A — Heart Rate Monitor (NodeMCU, ESP8266)
- Subsystem B — Sound Monitor (Arduino Uno)
- Data & ML — Raspberry Pi data collection, publisher, and laptop ML/subscriber workflows

Prerequisites
- Arduino IDE (for NodeMCU & Uno)
- Raspberry Pi with Python 3 (tested with 3.11)
- Mac laptop with Python 3 and scp
- Network connectivity between devices
- USB cables for micro-controllers

1. Environment / Board Setup

Subsystem A: Heart Rate Monitor (NodeMCU, ESP8266)
- Arduino IDE: File > Preferences > "Additional Boards Manager URLs":
  http://arduino.esp8266.com/stable/package_esp8266com_index.json
- Tools > Board > Boards Manager: search "esp8266" and install.
- Select Board: Tools > Board > NodeMCU 1.0 (ESP-12E Module).
- Required library: SparkFun MAX3010x Pulse and Proximity Sensor Library (SparkFun Electronics).

Subsystem B: Sound Monitor (Arduino Uno)
- Select Board: Tools > Board > Arduino AVR Boards > Arduino Uno.
- No external libraries required.

Raspberry Pi (Data collection & publisher)
- Ensure Python 3 installed (3.11 recommended).
- Scripts live in ~/Desktop/peojext/ (data_collector.py, publish.py).

2. How to Run

A) Subsystem A — Heart Rate (NodeMCU)
- Connect NodeMCU to your PC.
- Arduino IDE: Tools > Port -> select NodeMCU port.
- Open the Heart Rate .ino file and Upload.
- Open Serial Monitor at 115200 baud to view output.

B) Subsystem B — Sound Monitor (Arduino Uno)
- Connect Arduino Uno to your PC.
- Arduino IDE: Tools > Port -> select Arduino Uno port.
- Open Sound Monitor .ino and Upload.
- Open Serial Monitor at 115200 baud.

C) Subsystem C - Raspberry Pi — Data Collection & Publisher
- Data collection on the Pi:
  python3 ~/Desktop/peojext/data_collector.py
- Start publisher on the Pi:
  python3 ~/Desktop/peojext/publish.py

D) Laptop (Mac) — ML & Subscriber
- Copy CSV from Pi to Mac (adjust user/IP/path as needed):
  scp iot@192.168.1.162:/home/iot/door_env/lib/python3.11/site-packages/imu_training_data_v2.csv ~/Downloads/
- Run ML pipeline (on Mac):
  python3 machine_learning.py
- Run subscriber (on Mac):
  python3 project_sub.py

3. How to Interpret Outputs

Subsystem A: Heart Rate Output (NodeMCU)
- Data: Stabilized BPM (integer)
- Frequency: ~100 Hz (every ~10 ms)
- Format: one integer per line, e.g.:
  72
  72
  73
- Note: 0 indicates recalibration or no finger detected.

Subsystem B: Sound Output (Arduino Uno)
- Data: Peak sound amplitude (integer 0–1023)
- Frequency: ~150 Hz (every ~6.66 ms)
- Format: one integer per line, e.g.:
  12
  45
  1023
  56
- Meaning: higher numbers = louder sound peaks in the sampling window.

Subsystem C: Raspberry Pi / ML
- data_collector.py writes imu_training_data_v2.csv used by machine_learning.py.
- machine_learning.py loads CSV, trains/tests model(s) and prints results.

4. Project Layout (example)
- ~/Desktop/peojext/
  - data_collector.py
  - publish.py
- laptop/
  - machine_learning.py
  - project_sub.py
- Arduino/
  - heart_rate/HeartRate.ino
  - sound_monitor/SoundMonitor.ino

5. Notes & Troubleshooting
- Replace IP addresses, usernames, and paths for your environment.
- If scp shows "Permission denied": check SSH credentials and file permissions on the Pi.
- If Python reports missing modules: activate correct virtualenv or pip install dependencies.
- Ensure both devices are on the same network for publisher/subscriber communication.
- Use Serial Monitor at 115200 baud unless code specifies otherwise.



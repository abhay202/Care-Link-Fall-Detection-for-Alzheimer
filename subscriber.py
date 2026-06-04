import json
import time
import numpy as np
import joblib
import paho.mqtt.client as mqtt
import queue
import threading
import os
import sys
from collections import deque
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import ASYNCHRONOUS
from tslearn.preprocessing import TimeSeriesScalerMinMax
from tslearn.neighbors import KNeighborsTimeSeriesClassifier

NUM_WORKER_THREADS = 8
WINDOW_SIZE = 150

MQTT_TOPIC = "iot/fall_detection"
MQTT_BROKER = "d7321370b3574b00a42c844d38d02569.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.webclient.1761266141226"
MQTT_PASS = "81K#@DpMi;75aTH?fwCo"

INFLUX_URL = "https://us-east-1-1.aws.cloud2.influxdata.com"
INFLUX_TOKEN = "ojn0z-8QYcqRgFBkM5AhT77YkmFH_rPjYVc_d9F1p5dI4SBw3DjbmcqmO8g-xse4RmNozL_2aX8SGGe_ykV7yg=="
ORG = "NCSU"
BUCKET = "iot_data"

SCALER_FILENAME = "fast_scaler_v1.pkl"
MODEL_FILENAME = "fast_model_v1.pkl"
PUB_SOUND_KEY = 'sound'

device_buffers = {}
buffer_lock = threading.Lock()

client_influx = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=ORG)
write_api = client_influx.write_api(write_options=ASYNCHRONOUS)

if not os.path.exists(SCALER_FILENAME) or not os.path.exists(MODEL_FILENAME):
    sys.exit(1)

def processing_worker(worker_id, data_queue, model_path, scaler_path, write_api):
    try:
        local_clf = joblib.load(model_path)
        local_scaler = joblib.load(scaler_path)
    except:
        return

    while True:
        try:
            payload = data_queue.get()
            if payload is None:
                break

            try:
                data = json.loads(payload.decode())
            except:
                data_queue.task_done()
                continue

            device_id = data.get("device_id", "unknown_device")
            batch_list = data.get('data_batch', [])
            steps = data.get('steps', 0)
            ts_ms = data.get('batch_ts', int(time.time() * 1000))

            current_window_np = None
            with buffer_lock:
                if device_id not in device_buffers:
                    device_buffers[device_id] = deque(maxlen=WINDOW_SIZE)

                for sample in batch_list:
                    ax, ay, az = sample['ax'], sample['ay'], sample['az']
                    gx, gy, gz = sample['gx'], sample['gy'], sample['gz']
                    snd = sample.get(PUB_SOUND_KEY, 0)
                    device_buffers[device_id].append([ax, ay, az, gx, gy, gz, snd])

                if len(device_buffers[device_id]) == WINDOW_SIZE:
                    current_window_np = np.array(device_buffers[device_id])

            label_pred = "buffering"

            if current_window_np is not None:
                try:
                    accel = current_window_np[:, :3]
                    gyro = current_window_np[:, 3:6]

                    accel_mags = np.sqrt(np.sum(accel**2, axis=1))
                    gyro_mags = np.sqrt(np.sum(gyro**2, axis=1))

                    dynamic_range = np.max(accel_mags) - np.min(accel_mags)

                    if dynamic_range < 6.0:
                        label_pred = "inactivity"
                    else:
                        max_acc = np.max(accel_mags)
                        max_gyro = np.max(gyro_mags)

                        max_abs_az = np.max(np.abs(current_window_np[:, 2]))
                        max_abs_gy = np.max(np.abs(current_window_np[:, 4]))

                        is_fall = False

                        if max_acc > 70.0 and max_gyro > 140.0:
                            if max_abs_gy > 200.0:
                                is_fall = True
                            elif max_abs_az > 50.0:
                                is_fall = True
                        elif max_acc > 125.0:
                            is_fall = True

                        if is_fall:
                            label_pred = "fall"
                        else:
                            ts_reshaped = current_window_np.reshape(1, WINDOW_SIZE, 7)
                            ts_scaled = local_scaler.transform(ts_reshaped)
                            prediction = local_clf.predict(ts_scaled)[0]
                            label_pred = str(prediction)

                except:
                    label_pred = "error"

            try:
                bpm = int(batch_list[-1].get('bpm', 0)) if batch_list else 0
                snd_vals = [int(s.get('sound', 0)) for s in batch_list]
                max_sound = max(snd_vals) if snd_vals else 0
                if max_sound > 1023:
                    max_sound = 1023
            except:
                bpm = 0
                max_sound = 0

            if max_sound > 50 and label_pred != "fall":
                label_pred = "restlessness"

            try:
                point = (
                    Point("patient_activity")
                    .field("steps", int(steps))
                    .field("ml_label", label_pred)
                    .field("bpm", int(bpm))
                    .field("sound_level", int(max_sound))
                    .time(ts_ms, 'ms')
                )
                write_api.write(bucket=BUCKET, org=ORG, record=point)
            except:
                pass

        except:
            pass
        finally:
            data_queue.task_done()

def on_connect(client, userdata, flags, rc):
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    userdata['queue'].put(msg.payload)

if __name__ == "__main__":
    data_queue = queue.Queue()
    worker_threads = []

    for i in range(NUM_WORKER_THREADS):
        t = threading.Thread(
            target=processing_worker,
            args=(i, data_queue, MODEL_FILENAME, SCALER_FILENAME, write_api),
            daemon=True
        )
        t.start()
        worker_threads.append(t)

    mqtt_client = mqtt.Client(userdata={'queue': data_queue})
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
    mqtt_client.tls_set()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        mqtt_client.loop_stop()
        for _ in range(NUM_WORKER_THREADS):
            data_queue.put(None)
        for t in worker_threads:
            t.join()
        write_api.close()
        client_influx.close()

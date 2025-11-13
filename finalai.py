import paho.mqtt.client as mqtt
import json
import time
import struct
from datetime import datetime
import ssl
import numpy as np
from collections import deque
from queue import Queue, Empty
from threading import Thread
from typing import Optional
from pynq import Overlay, allocate


# =======================================================
# Ultra96 Hardware CNN Runner (blocking DMA, packet=4 frames)
# =======================================================
class Ultra96CNNRunner:
    def init(
        self,
        bitfile="cnn_overlay_10.xsa",
        meta_path="artifacts_tf/meta.json",
        pca_npz="artifacts_tf/pca_params_summarizer.npz",
        cnn_ip_name="cnn1d_ip_0",
        dma_name="axi_dma_0",
    ):
        print("[AI] Loading overlay...")
        self._ol = Overlay(bitfile)
        self._ol.download()
        print("[AI] Overlay loaded:", bitfile)

        # Hardware handles
        self._cnn = getattr(self._ol, cnn_ip_name)
        self._dma = getattr(self._ol, dma_name)

        # Arm CNN once — AP_START | AUTO_RESTART
        ctrl_before = self._cnn.read(0x00)
        self._cnn.write(0x00, 0x81)
        ctrl_after = self._cnn.read(0x00)
        print(f"[AI] CNN CTRL before=0x{ctrl_before:08X}, after=0x{ctrl_after:08X}")

        # Load preprocessing metadata
        with open(meta_path, "r") as f:
            meta = json.load(f)

        self.WINDOW = int(meta["window"])
        self.NUM_SEGMENTS = int(meta["num_segments"])
        self.STATS_LIST = list(meta["stats_list"])
        self.D_IN = int(meta["D_pca"])
        self.CLASSES = int(meta["classes"])
        self.class_names = list(meta.get("class_names", [str(i) for i in range(self.CLASSES)]))

        # PCA + scaler
        npz = np.load(pca_npz)
        self.scaler_mean = npz["scaler_mean"]
        self.scaler_scale = npz["scaler_scale"]
        self.pca_components = npz["pca_components"]
        self.pca_mean = npz["pca_mean"]

        print(f"[AI] Model expects D_IN={self.D_IN}, CLASSES={self.CLASSES}, WINDOW={self.WINDOW}")

        # Rolling window (stores latest WINDOW rows)
        self.FEATS_PER_ROW = 30
        self._buf = deque(maxlen=self.WINDOW)

        # DMA reusable buffers
        self._in_buf = allocate(shape=(self.D_IN,), dtype=np.float32)
        self._out_buf = allocate(shape=(self.CLASSES,), dtype=np.float32)

        # Behavior control variables
        self.last_raw_pred = 0         # last raw argmax
        self.prev_filtered_pred = 0    # last output after rules
        self.cooldown_until = 0        # next allowed non-zero prediction timestamp

        self.HOP = 4  # 4 frames per packet


    # ---------------- Window utilities ----------------
    def window_len(self): return len(self._buf)
    def window_size(self): return self.WINDOW
    def window_ready(self): return len(self._buf) >= self.WINDOW


    @staticmethod
    def readings_to_row(sensor_readings) -> np.ndarray:
        """Convert parsed IMU readings (dicts) into a flat 30-float row"""
        row = []
        for i in range(5):
            imu = next((r for r in sensor_readings if r.get("sensor_id") == i), None)
            if imu:
                acc = imu["acceleration"]; gyr = imu["gyroscope"]
                row.extend([float(acc["x"]), float(acc["y"]), float(acc["z"]),
                            float(gyr["x"]), float(gyr["y"]), float(gyr["z"])])
            else:
                row.extend([0.0] * 6)
        return np.array(row, dtype=np.float32)


    def push_row(self, row_30: np.ndarray):
        if row_30.shape[0] != self.FEATS_PER_ROW:
            raise ValueError(f"Row has {row_30.shape[0]} features; expected {self.FEATS_PER_ROW}")
        self._buf.append(row_30.astype(np.float32))# ---------- summarizer ----------
    def _summarize_window(self, win_2d: np.ndarray) -> np.ndarray:
        W = win_2d.shape[0]
        feats = []
        for s in range(self.NUM_SEGMENTS):
            a = round(s     * W / self.NUM_SEGMENTS)
            b = round((s+1) * W / self.NUM_SEGMENTS)
            seg = win_2d[a:b]
            parts = []
            if "mean"   in self.STATS_LIST: parts.append(seg.mean(axis=0))
            if "std"    in self.STATS_LIST: parts.append(seg.std(axis=0) + 1e-8)
            if "p2p"    in self.STATS_LIST: parts.append(seg.max(axis=0) - seg.min(axis=0))
            if "energy" in self.STATS_LIST: parts.append((seg**2).sum(axis=0))
            feats.append(np.concatenate(parts))
        return np.stack(feats).astype(np.float32)


    # ---------- scaler + pca ----------
    def _apply_scaler_pca(self, flat: np.ndarray) -> np.ndarray:
        flat = flat.reshape(-1).astype(np.float32, copy=False)

        assert flat.shape[0] == self.scaler_mean.shape[0], \
            f"Scaler expects {self.scaler_mean.shape[0]}, got {flat.shape[0]}"

        flat_scaled = (flat - self.scaler_mean) / self.scaler_scale
        flat_centered = flat_scaled - self.pca_mean

        x_pca = flat_centered.dot(self.pca_components.T).astype(np.float32, copy=False)

        assert x_pca.shape[-1] == self.D_IN, \
            f"PCA output {x_pca.shape[-1]} != expected {self.D_IN}"

        return x_pca


    @staticmethod
    def _softmax(v: np.ndarray) -> np.ndarray:
        v = v - np.max(v)
        e = np.exp(v).astype(np.float32, copy=False)
        return e / (np.sum(e) + 1e-9)


    # =======================================================
    #  ⬇️⬇️ MODIFIED PREDICTION LOGIC (threshold + debounce + cooldown)
    # =======================================================
    def infer_once(self) -> Optional[int]:
        if not self.window_ready():
            return None

        win = np.stack(self._buf, axis=0)
        seg = self._summarize_window(win)
        flat = seg.reshape(-1)
        xvec = self._apply_scaler_pca(flat)

        np.copyto(self._in_buf, xvec)

        try:
            self._dma.recvchannel.transfer(self._out_buf)
            self._dma.sendchannel.transfer(self._in_buf)
            self._dma.sendchannel.wait()
            self._dma.recvchannel.wait()
            _ = self._cnn.read(0x00)     # clear stale AP_DONE
        except Exception as e:
            print(f"[ERR] DMA transfer error: {e}")
            return None

        logits = np.copy(self._out_buf)
        probs = self._softmax(logits)

        raw_pred = int(np.argmax(probs))
        max_prob = float(probs[raw_pred])

        # ---------- (1) Confidence threshold ----------
        if raw_pred != 0 and max_prob < 0.50:
            raw_pred = 0

        # ---------- (2) Two consecutive non-zero predictions required ----------
        if raw_pred != 0 and raw_pred == self.last_raw_pred:
            confirmed_pred = raw_pred
        else:
            confirmed_pred = 0

        self.last_raw_pred = raw_pred

        # ---------- (3) Cooldown between non-zero outputs ----------
        now = time.time()
        if confirmed_pred != 0:
            if now < self.cooldown_until:
                confirmed_pred = 0
            else:
                self.cooldown_until = now + 5     # cooldown

        self.prev_filtered_pred = confirmed_pred
        return confirmed_pred


    def close(self):
        for b in (self._in_buf, self._out_buf):
            try: b.freebuffer()
            except: pass



# =======================================================
# MQTT Subscriber
# =======================================================
class Ultra96MQTTSubscriber:
    def init(self):
        self.session_counter = 1000

        self.MQTT_BROKER = "localhost"
        self.MQTT_PORT   = 8883

        self.topic_sensor_to_ultra96 = "robot/sensor/to_ultra96"
        self.topic_processed_data    = "ultra96/processed/to_firebeetle"
        self.TLS_CA   = "/etc/mosquitto/certs/ca.crt"
        self.TLS_CERT = "/etc/mosquitto/certs/ultra96.crt"
        self.TLS_KEY  = "/etc/mosquitto/certs/ultra96.key"

        self.client = mqtt.Client(client_id="ultra96_subscriber_tls", userdata=self)
        self.client.tls_set(
            ca_certs=self.TLS_CA,
            certfile=self.TLS_CERT,
            keyfile=self.TLS_KEY,
            tls_version=ssl.PROTOCOL_TLSv1_2,
        )
        self.client.tls_insecure_set(True)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.work_queue = Queue(maxsize=10)
        Thread(target=self._worker_loop, daemon=True).start()

        try:
            self.ai = Ultra96CNNRunner()
        except Exception as e:
            print(f"[ERROR] Could not init CNN runner: {e}")
            self.ai = None


    def on_connect(self, client, userdata, flags, rc):
        print("Connected." if rc == 0 else f"MQTT connect failed ({rc})")
        client.subscribe(self.topic_sensor_to_ultra96)
        print(f"Subscribed: {self.topic_sensor_to_ultra96}")


    @staticmethod
    def parse_packet_exact_4_frames(raw_data: bytes):
        expected = 4 * 5 * 6 * 4
        if len(raw_data) != expected:
            return None, f"Invalid packet size {len(raw_data)}, expected {expected}"

        frames = []
        off = 0
        for _ in range(4):
            frame = []
            for imu_id in range(5):
                vals = struct.unpack("!6f", raw_data[off:off+24])
                off += 24
                frame.append({
                    "sensor_id": imu_id,
                    "acceleration": {"x": vals[0], "y": vals[1], "z": vals[2]},
                    "gyroscope":    {"x": vals[3], "y": vals[4], "z": vals[5]},
                })
            frames.append(frame)
        return frames, None


    def on_message(self, client, userdata, msg):
        frames, err = self.parse_packet_exact_4_frames(msg.payload)
        if err: 
            print("[ERR]", err)
            return

        while not self.work_queue.empty():
            try: self.work_queue.get_nowait()
            except Empty: break

        self.work_queue.put_nowait((frames, self.session_counter))
        self.session_counter += 1


    def _worker_loop(self):
        while True:
            try:
                frames, sess = self.work_queue.get(timeout=1.0)
            except Empty:
                continue

            if not self.ai:
                continue

            # Add frames one by one → run inference per frame
            for sensor_readings in frames:
                self.ai.push_row(self.ai.readings_to_row(sensor_readings))
                pred = self.ai.infer_once()

                # ✅ PRINT ONLY WHEN NON-ZERO PREDICTION IS CONFIRMED
                if pred and pred != 0:
                    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    print(f"[PRED] {ts} → class={pred}")

                # ✅ Publish each frame’s result
                payload = {
                    "session": sess,
                    "prediction": -1 if pred is None else int(pred),
                    "status": "warming_up" if pred is None else "success",
                    "timestamp": datetime.now().isoformat(),
                }
                self.client.publish(self.topic_processed_data, json.dumps(payload), qos=1)



    def start(self):
        print("🔄 Connecting to MQTT broker...")

        max_retries = 1000
        attempt = 0

        while attempt < max_retries:
            try:
                self.client.connect(self.MQTT_BROKER, self.MQTT_PORT, 60)
                print("✅ Connected to MQTT broker.")
                break  # exit loop on successful connection

            except Exception as e:
                attempt += 1
                print(f"[MQTT] Connection failed (attempt {attempt}/{max_retries}): {e}")

                if attempt >= max_retries:
                    print("❌ Reached maximum retry count — giving up.")
                    return  # stop function entirelyprint("⏳ Retrying in 10 seconds...")
                time.sleep(10)

        # Only runs if connected
        self.client.loop_start()
        print("✅ MQTT loop started → waiting for packets...")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutdown requested…")
        finally:
            self.client.loop_stop()
            self.client.disconnect()
            if self.ai:
                self.ai.close()



if name == "main":
    print("=" * 60)
    print(" Ultra96 MQTT Subscriber + CNN (DMA, debounce, cooldown)")
    print("=" * 60)
    Ultra96MQTTSubscriber().start()
import subprocess
import time
import os
import signal
import sys

class MosquittoController:
    def __init__(self):
        self.mosquitto_process = None

    def start_mosquitto(self):
        """Start Mosquitto broker"""
        try:
            print("Starting Mosquitto MQTT broker with TLS...")
            
            # Start mosquitto with our config
            self.mosquitto_process = subprocess.Popen(
                ["mosquitto", "-c", "/etc/mosquitto/conf.d/tls.conf"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Wait briefly to see if it crashes immediately
            time.sleep(1)
            if self.mosquitto_process.poll() is not None:
                stdout, stderr = self.mosquitto_process.communicate()
                print("Mosquitto exited at startup")
                if stdout:
                    print("---- STDOUT ----")
                    print(stdout.decode())
                if stderr:
                    print("---- STDERR ----")
                    print(stderr.decode())
                return False

            print("Mosquitto broker started successfully")
            print("Listening on: 0.0.0.0:8883 (TLS)")
            print("TLS: Enabled")
            print("=" * 60)
            print("Waiting for FireBeetle and Ultra96 connections...")
            print("Press Ctrl+C to stop the broker")

            return True
        except Exception as e:
            print(f"Failed to start Mosquitto: {e}")
            return False

    def stop_mosquitto(self):
        """Stop Mosquitto broker"""
        if self.mosquitto_process:
            print("Stopping Mosquitto broker...")
            self.mosquitto_process.terminate()
            self.mosquitto_process.wait()
            print("Mosquitto broker stopped")

    def monitor_status(self):
        """Monitor and display broker status"""
        while True:
            try:
                # Check if mosquitto is still running
                if self.mosquitto_process and self.mosquitto_process.poll() is not None:
                    print("Mosquitto broker stopped unexpectedly")
                    break
                    
                time.sleep(2)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Monitoring error: {e}")
                break

    def start(self):
        """Start the broker controller"""
        if not self.start_mosquitto():
            return
        
        try:
            self.monitor_status()
        except KeyboardInterrupt:
            print("\nShutdown requested by user...")
        except Exception as e:
            print(f"Unexpected error: {e}")
        finally:
            self.stop_mosquitto()

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print('\nShutdown requested by user...')
    sys.exit(0)

if __name__ == "__main__":
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    print("Starting Mosquitto MQTT Broker Controller...")
    controller = MosquittoController()
    controller.start()
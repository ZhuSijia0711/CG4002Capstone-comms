#include <Wire.h>
#include <WiFi.h>
#include "MPU6050.h"

#define NUM_IMU 5
#define TCA_ADDR 0x70
#define MOTOR_PIN 9   // vibration motor pin (IO9)

// IMUs
MPU6050 imu[NUM_IMU];

// Conversion factors
#define ACCEL_SCALE 16384.0
#define GYRO_SCALE 131.0

float accelOffset[NUM_IMU][3] = {0};
float gyroOffset[NUM_IMU][3]  = {0};

// WiFi
const char* ssid = "iPhone";
const char* password = "zhuqshenw";
WiFiClient client;
const char* laptop_ip = "172.20.10.6"; // your PC IP
const int laptop_port = 4210;

// === Motor burst parameters ===
const int pulseDuration = 100;   // ms motor ON
const int gapDuration   = 100;   // ms motor OFF between pulses
const int numPulses     = 3;     // pulses per burst
const int burstInterval = 5000;  // ms between bursts

// State machine variables
int pulseCount = 0;
bool inBurst = false;
bool motorState = false; // true = ON, false = OFF
unsigned long lastMotorEvent = 0;

// === Functions ===
void tcaSelect(uint8_t channel) {
  if (channel > 7) return;
  Wire.beginTransmission(TCA_ADDR);
  Wire.write(1 << channel);
  Wire.endTransmission();
}

void calibrateIMU(int imuIndex) {
  long ax_sum=0, ay_sum=0, az_sum=0;
  long gx_sum=0, gy_sum=0, gz_sum=0;
  const int samples = 500;
  for (int i=0;i<samples;i++) {
    int16_t ax, ay, az, gx, gy, gz;
    imu[imuIndex].getMotion6(&ax,&ay,&az,&gx,&gy,&gz);
    ax_sum+=ax; ay_sum+=ay; az_sum+=az;
    gx_sum+=gx; gy_sum+=gy; gz_sum+=gz;
    delay(2);
  }
  accelOffset[imuIndex][0]=(float)ax_sum/samples;
  accelOffset[imuIndex][1]=(float)ay_sum/samples;
  accelOffset[imuIndex][2]=(float)az_sum/samples - ACCEL_SCALE;
  gyroOffset[imuIndex][0]=(float)gx_sum/samples;
  gyroOffset[imuIndex][1]=(float)gy_sum/samples;
  gyroOffset[imuIndex][2]=(float)gz_sum/samples;
}

void scanI2C() {
  Serial.println("Scanning I2C bus...");
  byte error, address;
  for(address = 1; address < 127; address++ ) {
    Wire.beginTransmission(address);
    error = Wire.endTransmission();
    if (error == 0) {
      Serial.print("I2C device found at address 0x");
      if (address < 16) Serial.print("0");
      Serial.print(address, HEX);
      Serial.println(" !");
    }
  }
  Serial.println("Scan complete.");
}

// === Setup ===
void setup() {
  Serial.begin(115200);
  Wire.begin();

  // Motor setup
  pinMode(MOTOR_PIN, OUTPUT);
  digitalWrite(MOTOR_PIN, LOW);

  // WiFi
  Serial.println("Connecting to WiFi...");
  WiFi.begin(ssid,password);
  while(WiFi.status()!=WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n✅ WiFi connected");
  Serial.print("ESP32 IP: "); Serial.println(WiFi.localIP());

  scanI2C(); // Scan all I2C devices

  // TCP connect
  if (!client.connect(laptop_ip, laptop_port)) {
    Serial.println("❌ Connection to laptop failed!");
  } else {
    Serial.println("✅ Connected to laptop via TCP");
  }

  // IMU init - test all TCA channels
  for (int i=0; i<8; i++) {
    tcaSelect(i);
    Serial.print("Testing TCA channel "); Serial.println(i);
    byte error, address;
    int foundDevices = 0;
    for(address = 1; address < 127; address++ ) {
      Wire.beginTransmission(address);
      error = Wire.endTransmission();
      if (error == 0 && address != 0x70) {
        Serial.print("  Found device at address 0x");
        if (address < 16) Serial.print("0");
        Serial.print(address, HEX);
        Serial.println(" !");
        foundDevices++;
      }
    }
    if (foundDevices == 0) {
      Serial.println("  No devices found on this channel");
    }
    delay(100);
  }

  // IMU init
  for (int i=0;i<NUM_IMU;i++) {
    imu[i].initialize();
    if (imu[i].testConnection()) {
      Serial.print("IMU "); Serial.print(i); Serial.println(" connected");
      calibrateIMU(i);
    } else {
      Serial.print("IMU "); Serial.print(i); Serial.println(" failed");
    }
    delay(200);
  }
}

// === Loop ===
void loop() {
  String packet = "";

  // Collect IMU data
  for (int i=0;i<NUM_IMU;i++) {
    tcaSelect(i);
    int16_t ax, ay, az, gx, gy, gz;
    imu[i].getMotion6(&ax,&ay,&az,&gx,&gy,&gz);

    float ax_g = (ax - accelOffset[i][0])/ACCEL_SCALE;
    float ay_g = (ay - accelOffset[i][1])/ACCEL_SCALE;
    float az_g = (az - accelOffset[i][2])/ACCEL_SCALE;
    float gx_dps = (gx - gyroOffset[i][0])/GYRO_SCALE;
    float gy_dps = (gy - gyroOffset[i][1])/GYRO_SCALE;
    float gz_dps = (gz - gyroOffset[i][2])/GYRO_SCALE;

    packet += "IMU"+String(i)+":";
    packet += String(ax_g,3)+","+String(ay_g,3)+","+String(az_g,3)+",";
    packet += String(gx_dps,3)+","+String(gy_dps,3)+","+String(gz_dps,3)+";";
  }

  // Send IMU data over TCP
  if (client.connected()) {
    client.print(packet);
  } else {
    Serial.println("⚠️ Disconnected, retrying...");
    if (client.connect(laptop_ip, laptop_port)) {
      Serial.println("✅ Reconnected to laptop");
    }
  }

  // === Motor burst logic ===
  unsigned long now = millis();
  if (!inBurst) {
    if (now - lastMotorEvent >= burstInterval) {
      inBurst = true;
      pulseCount = 0;
      motorState = true;
      digitalWrite(MOTOR_PIN, HIGH);
      lastMotorEvent = now;
    }
  } else {
    if (motorState && now - lastMotorEvent >= pulseDuration) {
      motorState = false;
      digitalWrite(MOTOR_PIN, LOW);
      lastMotorEvent = now;
      pulseCount++;
    } 
    else if (!motorState && now - lastMotorEvent >= gapDuration) {
      if (pulseCount < numPulses) {
        motorState = true;
        digitalWrite(MOTOR_PIN, HIGH);
        lastMotorEvent = now;
      } else {
        inBurst = false; // finished burst
      }
    }
  }

  delay(10); // small delay
}

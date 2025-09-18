#include <Wire.h>
#include <WiFi.h>
#include <AES.h>
#include "MPU6050.h"
#include <base64.h>

#define NUM_IMU 5
#define TCA_ADDR 0x70
#define AES_BLOCK_SIZE 16

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
const char* laptop_ip = "172.20.10.6"; 
const int laptop_port = 4210;

// AES
AES aes;
byte aes_key[16] = {0x2B,0x7E,0x15,0x16,0x28,0xAE,0xD2,0xA6,
                    0xAB,0xF7,0x15,0x88,0x09,0xCF,0x4F,0x3C};
byte aes_iv[16]  = {0x00,0x01,0x02,0x03,0x04,0x05,0x06,0x07,
                     0x08,0x09,0x0A,0x0B,0x0C,0x0D,0x0E,0x0F};

// Helper: select TCA channel
void tcaSelect(uint8_t channel) {
  if (channel > 7) return;
  Wire.beginTransmission(TCA_ADDR);
  Wire.write(1 << channel);
  Wire.endTransmission();
}

// PKCS7 + AES CBC + Base64
String encryptData(String plaintext) {
  int inputLength = plaintext.length();
  byte input[inputLength + 1];
  plaintext.getBytes(input, inputLength + 1);

  int paddedLength = ((inputLength + AES_BLOCK_SIZE - 1)/AES_BLOCK_SIZE) * AES_BLOCK_SIZE;
  byte paddedInput[paddedLength];
  memcpy(paddedInput, input, inputLength);
  byte padValue = paddedLength - inputLength;
  for (int i=inputLength; i<paddedLength; i++) paddedInput[i] = padValue;

  byte encrypted[paddedLength];
  aes.set_key(aes_key,16);

  //reset IV each time
  byte iv_copy[16];
  memcpy(iv_copy, aes_iv, 16);
  aes.cbc_encrypt(paddedInput, encrypted, paddedLength/16, aes_iv);

  return base64::encode(encrypted, paddedLength);
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  WiFi.begin(ssid,password);
  while(WiFi.status()!=WL_CONNECTED){ delay(500); Serial.print("."); }
  Serial.println("\n✅ WiFi connected");

  if (!client.connect(laptop_ip, laptop_port)) Serial.println("❌ TCP connect failed");
  else Serial.println("✅ Connected to laptop");

  // Initialize IMUs
  for (int i=0;i<NUM_IMU;i++){
    tcaSelect(i);
    imu[i].initialize();
    if (imu[i].testConnection()) Serial.print("IMU "); Serial.print(i); Serial.println(" connected");
  }
}

void loop() {
  String packet = "";

  for (int i=0;i<NUM_IMU;i++){
    tcaSelect(i);
    int16_t ax,ay,az,gx,gy,gz;
    imu[i].getMotion6(&ax,&ay,&az,&gx,&gy,&gz);

    float ax_g = ax/ACCEL_SCALE;
    float ay_g = ay/ACCEL_SCALE;
    float az_g = az/ACCEL_SCALE;
    float gx_dps = gx/GYRO_SCALE;
    float gy_dps = gy/GYRO_SCALE;
    float gz_dps = gz/GYRO_SCALE;

    packet += "IMU"+String(i)+":";
    packet += String(ax_g,3)+","+String(ay_g,3)+","+String(az_g,3)+",";
    packet += String(gx_dps,3)+","+String(gy_dps,3)+","+String(gz_dps,3)+";";
  }

  // Encrypt and send
  String encrypted = encryptData(packet);
  if(client.connected()){
    client.print(encrypted);
    client.print("\n");  // TCP delimiter
    Serial.println("📤 Sent: " + encrypted);
  } else {
    if(client.connect(laptop_ip,laptop_port)) Serial.println("✅ Reconnected");
  }

  delay(1000);
}
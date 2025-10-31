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
byte aes_key[16] = {
  0x2B,0x7E,0x15,0x16,0x28,0xAE,0xD2,0xA6,
  0xAB,0xF7,0x15,0x88,0x09,0xCF,0x4F,0x3C
};
byte aes_iv[16]  = {
  0x00,0x01,0x02,0x03,0x04,0x05,0x06,0x07,
  0x08,0x09,0x0A,0x0B,0x0C,0x0D,0x0E,0x0F
};

// TCP receive buffer
String recvBuffer = "";
unsigned long lastRecvTime = 0;
const unsigned long RECV_TIMEOUT = 2000; // 2s timeout

// ====== TCA Multiplexer ======
void tcaSelect(uint8_t channel) {
  if (channel > 7) return;
  Wire.beginTransmission(TCA_ADDR);
  Wire.write(1 << channel);
  Wire.endTransmission();
}

// ====== BASE64 DECODE HELPER ======
int base64DecodeBytes(byte* output, const char* input, int inputLen) {
  int i = 0, j = 0, in_ = 0;
  byte char_array_4[4], char_array_3[3];
  const char* base64_chars =
      "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

  auto is_base64 = [](unsigned char c) {
    return (isalnum(c) || (c == '+') || (c == '/'));
  };

  while (inputLen-- && (input[in_] != '=') && is_base64(input[in_])) {
    char_array_4[i++] = input[in_];
    in_++;
    if (i == 4) {
      for (i = 0; i < 4; i++)
        char_array_4[i] = strchr(base64_chars, char_array_4[i]) - base64_chars;

      char_array_3[0] = (char_array_4[0] << 2) + ((char_array_4[1] & 0x30) >> 4);
      char_array_3[1] = ((char_array_4[1] & 0xf) << 4) + ((char_array_4[2] & 0x3c) >> 2);
      char_array_3[2] = ((char_array_4[2] & 0x3) << 6) + char_array_4[3];

      for (i = 0; (i < 3); i++) output[j++] = char_array_3[i];
      i = 0;
    }
  }

  if (i) {
    for (int k = i; k < 4; k++) char_array_4[k] = 0;
    for (int k = 0; k < 4; k++)
      char_array_4[k] = strchr(base64_chars, char_array_4[k]) - base64_chars;

    char_array_3[0] = (char_array_4[0] << 2) + ((char_array_4[1] & 0x30) >> 4);
    char_array_3[1] = ((char_array_4[1] & 0xf) << 4) + ((char_array_4[2] & 0x3c) >> 2);
    char_array_3[2] = ((char_array_4[2] & 0x3) << 6) + char_array_4[3];

    for (int k = 0; (k < i - 1); k++) output[j++] = char_array_3[k];
  }

  return j;
}

// ====== AES ENCRYPTION ======
String encryptData(String plaintext) {
  int inputLength = plaintext.length();
  byte input[inputLength + 1];
  plaintext.getBytes(input, inputLength + 1);

  int paddedLength = ((inputLength + AES_BLOCK_SIZE) / AES_BLOCK_SIZE) * AES_BLOCK_SIZE;
  byte paddedInput[paddedLength];
  memcpy(paddedInput, input, inputLength);

  // PKCS7 padding
  byte padValue = paddedLength - inputLength;
  for (int i = inputLength; i < paddedLength; i++) paddedInput[i] = padValue;

  byte encrypted[paddedLength];
  aes.set_key(aes_key, 16);
  byte iv_copy[16];
  memcpy(iv_copy, aes_iv, 16);
  aes.cbc_encrypt(paddedInput, encrypted, paddedLength / 16, iv_copy);

  return base64::encode(encrypted, paddedLength);
}

// ====== AES DECRYPTION ======
String decryptData(String encrypted_b64) {
  int inputLen = encrypted_b64.length();
  byte decoded[inputLen];
  int decodedLen = base64DecodeBytes(decoded, encrypted_b64.c_str(), inputLen);
  if (decodedLen <= 0) {
    Serial.println("Base64 decode failed");
    return "";
  }

  byte decrypted[decodedLen];
  aes.set_key(aes_key, 16);
  byte iv_copy[16];
  memcpy(iv_copy, aes_iv, 16);
  int blocks = (decodedLen + 15) / 16;
  aes.cbc_decrypt(decoded, decrypted, blocks, iv_copy);

  // Remove PKCS7 padding
  byte padValue = decrypted[decodedLen - 1];
  int plaintextLen = decodedLen - ((padValue > 0 && padValue <= AES_BLOCK_SIZE) ? padValue : 0);

  String plaintext = "";
  for (int i = 0; i < plaintextLen; i++) plaintext += (char)decrypted[i];
  return plaintext;
}

// ====== TCP RECEIVE HANDLER ======
void handleIncomingData() {
  while (client.available() > 0) {
    char c = client.read();
    if (c == '\n') {
      String incoming = recvBuffer;
      recvBuffer = "";
      incoming.trim();
      if (incoming.length() > 0) {
        String decrypted = decryptData(incoming);
        if (decrypted.length() > 0) {
          Serial.print("📩 Received (decrypted): ");
          Serial.println(decrypted);
        }
      }
      lastRecvTime = millis();
    } else {
      recvBuffer += c;
      if (recvBuffer.length() > 1024) {
        Serial.println("⚠️ Buffer overflow, clearing.");
        recvBuffer = "";
      }
    }
  }

  if (recvBuffer.length() > 0 && millis() - lastRecvTime > RECV_TIMEOUT) {
    Serial.println("⚠️ Incomplete message timeout, clearing buffer.");
    recvBuffer = "";
  }
}

// ====== SETUP ======
void setup() {
  Serial.begin(115200);
  Wire.begin();

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n✅ WiFi connected");

  if (!client.connect(laptop_ip, laptop_port))
    Serial.println("❌ TCP connect failed");
  else
    Serial.println("✅ Connected to laptop");

  for (int i = 0; i < NUM_IMU; i++) {
    tcaSelect(i);
    imu[i].initialize();
    if (imu[i].testConnection()) {
      Serial.print("IMU ");
      Serial.print(i);
      Serial.println(" connected");
    }
  }
}

// ====== LOOP ======
void loop() {
  String packet = "";
  for (int i = 0; i < NUM_IMU; i++) {
    tcaSelect(i);
    int16_t ax, ay, az, gx, gy, gz;
    imu[i].getMotion6(&ax, &ay, &az, &gx, &gy, &gz);

    float ax_g = ax / ACCEL_SCALE;
    float ay_g = ay / ACCEL_SCALE;
    float az_g = az / ACCEL_SCALE;
    float gx_dps = gx / GYRO_SCALE;
    float gy_dps = gy / GYRO_SCALE;
    float gz_dps = gz / GYRO_SCALE;

    packet += "IMU" + String(i) + ":";
    packet += String(ax_g, 3) + "," + String(ay_g, 3) + "," + String(az_g, 3) + ",";
    packet += String(gx_dps, 3) + "," + String(gy_dps, 3) + "," + String(gz_dps, 3) + ";";
  }

  String encrypted = encryptData(packet);
  if (client.connected()) {
    client.write(encrypted.c_str(), encrypted.length());
    client.write("\n");
    Serial.println("📤 Sent IMU data (encrypted)");
  } else {
    if (client.connect(laptop_ip, laptop_port)) Serial.println("✅ Reconnected");
  }

  handleIncomingData();
  delay(10);
}

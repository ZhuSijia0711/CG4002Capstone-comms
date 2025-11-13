#include <Wire.h>
#include <WiFi.h>
#include <AES.h>
#include "MPU6050.h"

#define NUM_IMU 5
#define TCA_ADDR 0x70
#define FUEL_ADDR 0x36
#define MOTOR_PIN 2   // vibration motor pin
#define AES_BLOCK_SIZE 16
#define N_SETS_PER_PACKET 4   

MPU6050 imu[NUM_IMU];

// Conversion factors
#define ACCEL_SCALE 16384.0
#define GYRO_SCALE 131.0

float accelOffset[NUM_IMU][3] = {0};
float gyroOffset[NUM_IMU][3]  = {0};

// WiFi
const char* ssid = "iPhone";
const char* password = "zhuqshenw";

// === IMU DATA SENDING CLIENT (to laptop) ===
WiFiClient dataClient;
const char* laptop_ip = "172.20.10.6"; 
const int data_port = 4210; // Port for sending IMU data

// === COMMAND RECEIVING SERVER (from laptop) ===
WiFiServer commandServer(5001);
WiFiClient commandClient;
bool commandClientConnected = false;

// AES (for IMU data encryption only)
AES aes;
byte aes_key[16] = {0x2B,0x7E,0x15,0x16,0x28,0xAE,0xD2,0xA6,
                    0xAB,0xF7,0x15,0x88,0x09,0xCF,0x4F,0x3C};
byte aes_iv[16]  = {0x00,0x01,0x02,0x03,0x04,0x05,0x06,0x07,
                    0x08,0x09,0x0A,0x0B,0x0C,0x0D,0x0E,0x0F};

// XOR Key for movement commands (must match Python code)
byte xor_key[16] = {'C','G','4','0','0','2','R','o','b','o','t','2','0','2','4','!'};

// === Motor buzz parameters ===
#define BUZZ_DEFAULT 500  // Standard buzz duration 
#define BUZZ_SHORT 120    // Standard short acknowledgement buzz for commands 1-6

bool motorBuzzing = false;
unsigned long motorStartTime = 0;
unsigned int currentBuzzDuration = BUZZ_DEFAULT; 

// Helper: select TCA channel
void tcaSelect(uint8_t channel) {
  if (channel > 7) return;
  Wire.beginTransmission(TCA_ADDR);
  Wire.write(1 << channel);
  Wire.endTransmission();
}

// === MAX17043 fuel gauge read voltage ===
float readFuelVoltage() {
  tcaSelect(5); // channel for fuel gauge
  Wire.beginTransmission((uint8_t)FUEL_ADDR);
  Wire.write(0x02); // VCELL register
  Wire.endTransmission(false);
  
  Wire.requestFrom((uint8_t)FUEL_ADDR, (uint8_t)2);

  if (Wire.available() == 2) {
    uint8_t msb = Wire.read();
    uint8_t lsb = Wire.read();
    uint16_t raw = (msb << 8) | lsb;
    float voltage = (raw >> 4) * 0.00125; // volts
    return voltage;
  }
  return 0.0; // Return 0 on read failure
}

// === MAX17043 fuel gauge read percentage ===
float readFuelPercentage() {
  tcaSelect(5); // channel for fuel gauge
  Wire.beginTransmission((uint8_t)FUEL_ADDR);
  Wire.write(0x04); // SOC register
  Wire.endTransmission(false);
  
  Wire.requestFrom((uint8_t)FUEL_ADDR, (uint8_t)2);

  if (Wire.available() == 2) {
    uint8_t msb = Wire.read();
    uint8_t lsb = Wire.read();
    uint16_t raw = (msb << 8) | lsb;
    float soc = (raw >> 8); // upper byte is percentage (0-100)
    return soc;
  }
  return 0.0; // Return 0 on read failure
}

// === Motor control functions ===
void startMotorBuzz(unsigned int duration) {
  if (!motorBuzzing) {
    currentBuzzDuration = duration;
    digitalWrite(MOTOR_PIN, HIGH);
    motorStartTime = millis();
    motorBuzzing = true;
    Serial.println("✅ Motor ON for " + String(duration) + "ms");
  }
}

void updateMotorBuzz() {
  if(motorBuzzing && millis() - motorStartTime >= currentBuzzDuration){
    digitalWrite(MOTOR_PIN, LOW);
    motorBuzzing = false;
  }
}

// Simple XOR encryption/decryption (no Base64)
String xor_crypt(String input) {
  String output = "";
  int key_length = 16;
  
  for (int i = 0; i < input.length(); i++) {
    char encrypted_char = input.charAt(i) ^ xor_key[i % key_length];
    output += encrypted_char;
  }
  
  return output;
}

// Simple function to convert string to hex (for debugging)
String stringToHex(String input) {
  String hexString = "";
  for (int i = 0; i < input.length(); i++) {
    char c = input.charAt(i);
    if (c < 16) hexString += "0";
    hexString += String(c, HEX);
  }
  return hexString;
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  
  // Initialize motor pin
  pinMode(MOTOR_PIN, OUTPUT);
  digitalWrite(MOTOR_PIN, LOW);
  
  WiFi.begin(ssid,password);
  while(WiFi.status()!=WL_CONNECTED){ delay(500); Serial.print("."); }
  Serial.println("\n✅ WiFi connected. IP: " + WiFi.localIP().toString());

  // === 1. IMU Data Client Connection ===
  if (!dataClient.connect(laptop_ip, data_port)) Serial.println("❌ IMU Data Client connect failed");
  else Serial.println("✅ IMU Data Client connected to laptop at " + String(laptop_ip) + ":" + String(data_port));

  // === 2. Command Server Initialization ===
  commandServer.begin();
  Serial.println("📡 Command Server started on port 5001");

  // Initialize IMUs
  for (int i=0;i<NUM_IMU;i++){
    tcaSelect(i);
    imu[i].initialize();
    if (imu[i].testConnection()) Serial.print("IMU "); Serial.print(i); Serial.println(" connected");
  }
}

void loop() {
  // === 1. COMMAND RECEIVING SERVER MANAGEMENT ===
  
  // Handle new client connections
  if (!commandClientConnected) {
    commandClient = commandServer.available();
    if (commandClient) {
      commandClientConnected = true;
      Serial.println("✅ Command Client connected (Laptop -> Glove)");
    }
  }

  // Check for and process incoming commands
  if (commandClientConnected && commandClient.connected()) {
    if (commandClient.available()) {
      // Read the incoming XOR-encrypted command line
      String encryptedCommand = commandClient.readStringUntil('\n');
      encryptedCommand.trim();
      
      Serial.println("🔐 Received XOR-encrypted command (hex): " + stringToHex(encryptedCommand));

      // XOR Decrypt the command (XOR is symmetric - same function for encrypt/decrypt)
      String decryptedCommand = xor_crypt(encryptedCommand);
      decryptedCommand.trim();
      
      Serial.println("🔓 Decrypted command: '" + decryptedCommand + "'");

      // Process decrypted command
      if (decryptedCommand.equalsIgnoreCase("come_here") || decryptedCommand.equalsIgnoreCase("forward") || decryptedCommand.equalsIgnoreCase("come") || decryptedCommand == "1" ||
          decryptedCommand.equalsIgnoreCase("go_away") || decryptedCommand.equalsIgnoreCase("backward") || decryptedCommand.equalsIgnoreCase("go") || decryptedCommand == "2" ||
          decryptedCommand.equalsIgnoreCase("turn_around") || decryptedCommand.equalsIgnoreCase("turn") || decryptedCommand == "3" ||
          decryptedCommand.equalsIgnoreCase("pet") || decryptedCommand == "4" ||
          decryptedCommand.equalsIgnoreCase("feed") || decryptedCommand == "5" ||
          decryptedCommand.equalsIgnoreCase("throw_ball") || decryptedCommand.equalsIgnoreCase("throw") || decryptedCommand == "6")
      {
        Serial.println("📢 Received movement/action command (1-6). Buzzing SHORT!");
        startMotorBuzz(BUZZ_SHORT);
      } 
      else if (decryptedCommand.equalsIgnoreCase("stop") || decryptedCommand == "0") {
        Serial.println("📢 Received STOP command (0). No buzz.");
      }
      else if (decryptedCommand.equalsIgnoreCase("BUZZ")) {
        Serial.println("📢 Received BUZZ (legacy) command!");
        startMotorBuzz(BUZZ_DEFAULT); 
      } 
      else if (decryptedCommand.length() > 0) {
        Serial.println("❌ Unknown decrypted command: '" + decryptedCommand + "'");
      }
      
      // Send ACK back
      commandClient.println("ACK:Command received and XOR-decrypted");
    }
  }
  
  // Handle command client disconnection
  if (commandClientConnected && !commandClient.connected()) {
    commandClient.stop();
    commandClientConnected = false;
    Serial.println("⚠️ Command Client disconnected");
  }

  // === 2. IMU DATA SENDING CLIENT MANAGEMENT ===
  // (Keep your existing IMU data sending code here - unchanged)
  // Since we removed the AES encryption for IMU data, you'll need to either:
  // 1. Keep using AES for IMU data (recommended) or 
  // 2. Use plaintext for IMU data temporarily
  
  // For now, let's just send plaintext IMU data:
  String packet = "";

  for (int set = 0; set < N_SETS_PER_PACKET; set++) {
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
  }

  // Add battery data to the packet
  float voltage = readFuelVoltage();
  float percent = readFuelPercentage();
  packet += "Fuel:" + String(voltage, 3) + "V," + String(percent, 0) + "%;";

  // Send plaintext IMU data for now
  if (dataClient.connected()) {
    dataClient.print(packet);
    dataClient.print("\n");
  } else {
    if (dataClient.connect(laptop_ip, data_port))
      Serial.println("✅ Reconnected to IMU Data Server");
  }

  // === 3. Motor Management ===
  updateMotorBuzz(); 

  delay(10);
}
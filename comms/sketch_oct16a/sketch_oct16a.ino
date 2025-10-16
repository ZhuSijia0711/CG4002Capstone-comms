#include <WiFi.h>
#include <WiFiUDP.h>

// ---------------- Wi-Fi Configuration ----------------
const char* ssid = "iPhone";
const char* password = "zhuqshenw";

// ---------------- TCP Server Configuration ----------------
WiFiServer server(5000);
WiFiClient tcpClient;
bool tcpClientConnected = false;

// ---------------- UDP Configuration ----------------
WiFiUDP udp;
const unsigned int localPort = 4210;
char incomingPacket[255];

// ---------------- Simple XOR Encryption ----------------
const byte xorKey[16] = { 
  0x55, 0xAA, 0x33, 0xCC, 0x0F, 0xF0, 0x99, 0x66,
  0x12, 0x34, 0x56, 0x78, 0xAB, 0xCD, 0xEF, 0x01
};

// ---------------- Motor Pin Configuration ----------------
#define LEFT_IN1 27
#define LEFT_IN2 26
#define RIGHT_IN1 13
#define RIGHT_IN2 5

void setup() {
  Serial.begin(115200);
  delay(2000);
  
  Serial.println("🚀 FireBeetle starting...");
  Serial.println("🔓 Using XOR encryption for testing");

  // Initialize motor pins
  pinMode(LEFT_IN1, OUTPUT);
  pinMode(LEFT_IN2, OUTPUT);
  pinMode(RIGHT_IN1, OUTPUT);
  pinMode(RIGHT_IN2, OUTPUT);
  stopMotors();

  // Connect to Wi-Fi
  WiFi.begin(ssid, password);
  Serial.print("Connecting to Wi-Fi");
  
  int retries = 0;
  while (WiFi.status() != WL_CONNECTED && retries < 20) {
    delay(500);
    Serial.print(".");
    retries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✅ Wi-Fi connected");
    Serial.print("📡 IP Address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n❌ Wi-Fi connection failed");
    ESP.restart();
  }

  // Start TCP server
  server.begin();
  Serial.println("📡 TCP server started on port 5000");
  
  // Start UDP
  udp.begin(localPort);
  Serial.print("📡 UDP server started on port "); 
  Serial.println(localPort);
  
  Serial.println("✅ System ready for connections");
}

void loop() {
  // Handle TCP connections and encrypted commands
  handleTCP();
  
  // Handle UDP commands for motor control
  handleUDP();
  
  delay(50);
}

void handleTCP() {
  // Handle new TCP client connections
  if (!tcpClientConnected) {
    tcpClient = server.available();
    if (tcpClient) {
      tcpClientConnected = true;
      Serial.println("✅ TCP Client connected");
    }
  }

  // Handle data from connected TCP client
  if (tcpClientConnected && tcpClient.connected()) {
    if (tcpClient.available() > 0) {
      // Read all available bytes
      int availableBytes = tcpClient.available();
      byte encrypted[availableBytes];
      byte decrypted[availableBytes];
      
      // Read encrypted data
      int readBytes = tcpClient.readBytes(encrypted, availableBytes);
      
      Serial.print("🔒 Received ");
      Serial.print(readBytes);
      Serial.print(" bytes: ");
      for(int i = 0; i < readBytes; i++) {
        if(encrypted[i] < 0x10) Serial.print("0");
        Serial.print(encrypted[i], HEX);
        Serial.print(" ");
      }
      Serial.println();

      // Simple XOR decryption
      for(int i = 0; i < readBytes; i++) {
        decrypted[i] = encrypted[i] ^ xorKey[i % 16]; // Use modulo to cycle through key
      }

      Serial.print("🔓 Decrypted bytes: ");
      for(int i = 0; i < readBytes; i++) {
        if(decrypted[i] < 0x10) Serial.print("0");
        Serial.print(decrypted[i], HEX);
        Serial.print(" ");
      }
      Serial.println();

      // Convert to string and parse commands
      String message = "";
      for(int i = 0; i < readBytes; i++) {
        if(decrypted[i] >= 32 && decrypted[i] <= 126) { // Printable ASCII
          message += (char)decrypted[i];
        } else if(decrypted[i] == 0) {
          break; // Null terminator
        }
      }
      
      message.trim();
      
      if (message.length() > 0) {
        Serial.print("📝 Decrypted message: '");
        Serial.print(message);
        Serial.println("'");

        // Execute command from TCP
        executeCommand(message);

        // Send ACK
        tcpClient.print("ACK:");
        tcpClient.println(message);
      }
    }
  }

  // Handle TCP client disconnection
  if (tcpClientConnected && !tcpClient.connected()) {
    tcpClient.stop();
    tcpClientConnected = false;
    Serial.println("⚠️ TCP Client disconnected");
  }
}

void handleUDP() {
  int packetSize = udp.parsePacket();
  if (packetSize) {
    int len = udp.read(incomingPacket, 255);
    if (len > 0) incomingPacket[len] = 0;
    String command = String(incomingPacket);
    command.trim();
    Serial.print("📡 Received UDP command: ");
    Serial.println(command);

    // Execute command from UDP
    executeCommand(command);
  }
}

void executeCommand(String command) {
  command.toLowerCase();
  command.trim();
  
  Serial.print("🎯 Executing command: '");
  Serial.print(command);
  Serial.println("'");

  // Enhanced command parsing with better matching
  if (command == "come_here" || command == "forward" || command == "come" || command == "1") {
    moveForwardShort();
  } else if (command == "go_away" || command == "backward" || command == "go" || command == "2") {
    moveBackwardShort();
  } else if (command == "turn_around" || command == "turn" || command == "3") {
    turnAround();
  } else if (command == "pet" || command == "4") {
    petAction();
  } else if (command == "feed" || command == "5") {
    feedAction();
  } else if (command == "stop" || command == "0") {
    stopMotors();
  } else {
    Serial.print("❌ Unknown command: '");
    Serial.print(command);
    Serial.println("'");
    Serial.println("💡 Available commands: come_here, go_away, turn_around, pet, feed, stop");
    Serial.println("💡 Or numeric: 1=forward, 2=backward, 3=turn, 4=pet, 5=feed, 0=stop");
  }
}

// --- Motor Control Functions ---
void stopMotors() {
  digitalWrite(LEFT_IN1, LOW);
  digitalWrite(LEFT_IN2, LOW);
  digitalWrite(RIGHT_IN1, LOW);
  digitalWrite(RIGHT_IN2, LOW);
  Serial.println("🛑 Motors stopped");
}

void moveForwardShort() {
  Serial.println("⬆️ Moving forward");
  digitalWrite(LEFT_IN1, HIGH); 
  digitalWrite(LEFT_IN2, LOW);
  digitalWrite(RIGHT_IN1, HIGH); 
  digitalWrite(RIGHT_IN2, LOW);
  delay(500);
  stopMotors();
}

void moveBackwardShort() {
  Serial.println("⬇️ Moving backward");
  digitalWrite(LEFT_IN1, LOW); 
  digitalWrite(LEFT_IN2, HIGH);
  digitalWrite(RIGHT_IN1, LOW); 
  digitalWrite(RIGHT_IN2, HIGH);
  delay(500);
  stopMotors();
}

void turnAround() {
  Serial.println("🔄 Turning around");
  digitalWrite(LEFT_IN1, HIGH); 
  digitalWrite(LEFT_IN2, LOW);
  digitalWrite(RIGHT_IN1, LOW); 
  digitalWrite(RIGHT_IN2, HIGH);
  delay(700);
  stopMotors();
}

void petAction() {
  Serial.println("🐾 Pet action");
  for (int i = 0; i < 3; i++) {
    moveForwardShort();
    delay(100);
    moveBackwardShort();
    delay(100);
  }
}

void feedAction() {
  Serial.println("🍖 Feed action");
  moveForwardShort();
}
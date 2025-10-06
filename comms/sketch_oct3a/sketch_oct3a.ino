#include <WiFi.h>
#include <PubSubClient.h>
#include <WiFiClientSecure.h>

// WiFi credentials
const char* ssid = "iPhone";
const char* password = "zhuqshenw";

// MQTT Configuration
const char* mqtt_broker = "172.17.183.135";
const int mqtt_port = 8883;
const char* topic_processed_data = "robot/movement/data";

// Your CA Certificate
const char* ca_cert = \
"-----BEGIN CERTIFICATE-----\n" \
"MIIDqTCCApGgAwIBAgIUOWOi7UYQOR3qquM2WHADmiX6pmowDQYJKoZIhvcNAQEL\n" \
"BQAwZDELMAkGA1UEBhMCU0cxCzAJBgNVBAgMAlNHMQwwCgYDVQQKDANOVVMxFzAV\n" \
"BgNVBAMMDk1RVFQgQ0EgU2VydmVyMSEwHwYJKoZIhvcNAQkBFhJlMDk2ODExNkB1\n" \
"Lm51cy5lZHUwHhcNMjUwOTEyMDQwNTIzWhcNMzUwOTEwMDQwNTIzWjBkMQswCQYD\n" \
"VQQGEwJTRzELMAkGA1UECAwCU0cxDDAKBgNVBAoMA05VUzEXMBUGA1UEAwwOTVFU\n" \
"VCBDQSBTZXJ2ZXIxITAfBgkqhkiG9w0BCQEWEmUwOTY4MTE2QHUubnVzLmVkdTCC\n" \
"ASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBALR11TL3yadhc+3PYxaboY8g\n" \
"GbvI3VTAIoUSkC9hOx8DjYIY0almGbFJuZrhLhSMKRBCKcdwR0yzD+pjsxe81BXM\n" \
"2PYaAlgyv/fEBhoQSZ/BLJilnxHtENdnv11brrDoYcjtisSOrlKCrozfzjxrtYoZ\n" \
"K5acjIAJz5kqcYywJDT9TvGL0/8dcXtscHFGSR7oUVXEh7hU1LibKnfaOWn8F/p+\n" \
"rVBJlXPfx0bR+s3DOW5sH1Ragk94ySr7wZLc9IQ8vdN590ujza/9etMNFZ4AbgbX\n" \
"gdd/xsaWgF03ZBgDDd+NkcsxNnmynZc7m8q1BLaODsmhHF5fzbRYZQPPY3OcWpsC\n" \
"AwEAAaNTMFEwHQYDVR0OBBYEFDWm4SDWLEdniZFLkcuwRv7kwpsVMB8GA1UdIwQY\n" \
"MBaAFDWm4SDWLEdniZFLkcuwRv7kwpsVMA8GA1UdEwEB/wQFMAMBAf8wDQYJKoZI\n" \
"hvcNAQELBQADggEBAEvf4rrJx17o8iHQpVXUalRVbOHCXacE2PbK1bD1ZUcoZ7Bb\n" \
"w6s37L3yjPCNvCK4dpnC8iA7YbuFBghLgwkgtT5s1hNBI8ylpimGasZNKbIW7qlO\n" \
"zKj21vJzgR8GJIfe1t90GNZ9DXe4hqavwbASLiNijtgaRQ6Xjs7dmqj2ZX36duGX\n" \
"pnHQb7dAGx0Mhtku5oD5Z+Iz4a3s65aiubLkphw6pZ9ImVPpAh5QPmq23I8ZXUvj\n" \
"XHR1+h0QedQ0vyCEo/PZd5f4DGRVvNvkULvS9wlFsKSv7odnJMHoZLo1N+yL/tEx\n" \
"gZNrO3Y417BsGxlWWc7s5QbVPhHJlNEh53PQKHg=\n" \
"-----END CERTIFICATE-----\n";

WiFiClientSecure espClient;
PubSubClient client(espClient);

const char* movement_classes[] = {"STOP", "FORWARD", "BACKWARD", "TURN"};
int current_movement = 0;
unsigned long last_message_time = 0;
int message_count = 0;

void setup_wifi() {
  Serial.begin(115200);
  delay(10);
  
  Serial.println();
  Serial.println("FireBeetle ESP32 - Continuous Integer Receiver");
  Serial.println("================================================");
  
  Serial.print("Connecting to: ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println();
  Serial.println("WiFi connected");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

void callback(char* topic, byte* payload, unsigned int length) {
  // This runs CONTINUOUSLY whenever a new message arrives
  
  String message = "";
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  
  message_count++;
  last_message_time = millis();
  
  Serial.print("[");
  Serial.print(message_count);
  Serial.print("] Received: ");
  Serial.println(message);
  
  // Process the integer
  if (strcmp(topic, topic_processed_data) == 0) {
    int movement = message.toInt();
    if (movement >= 0 && movement <= 3) {
      current_movement = movement;
      Serial.print("Movement: ");
      Serial.print(movement);
      Serial.print(" - ");
      Serial.println(movement_classes[movement]);
      executeMovement(movement);
    } else {
      Serial.println("Invalid movement received");
    }
  }
}

void executeMovement(int movement) {
  switch(movement) {
    case 0:
      Serial.println("ACTION: STOP");
      break;
    case 1:
      Serial.println("ACTION: FORWARD");
      break;
    case 2:
      Serial.println("ACTION: BACKWARD");
      break;
    case 3:
      Serial.println("ACTION: TURN");
      break;
  }
}

void reconnect() {
  // Loop until we're reconnected
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection... ");
    
    String clientId = "FireBeetle-";
    clientId += String(random(0xffff), HEX);
    
    if (client.connect(clientId.c_str())) {
      Serial.println("Connected to MQTT broker");
      
      // Subscribe to topic - THIS IS CRITICAL for continuous reception
      if (client.subscribe(topic_processed_data)) {
        Serial.print("Subscribed to: ");
        Serial.println(topic_processed_data);
        Serial.println("Ready to receive integers continuously...");
      } else {
        Serial.println("Subscription failed!");
      }
      
    } else {
      Serial.print("Failed, rc=");
      Serial.print(client.state());
      Serial.println(" - retrying in 5 seconds");
      delay(5000);
    }
  }
}

void setup() {
  setup_wifi();
  
  // Setup TLS
  espClient.setCACert(ca_cert);
  Serial.println("CA certificate loaded");
  
  // Setup MQTT client
  client.setServer(mqtt_broker, mqtt_port);
  client.setCallback(callback);
  client.setKeepAlive(60);
  
  // Initial connection
  reconnect();
  
  Serial.println();
  Serial.println("FireBeetle ready - waiting for integer messages...");
  Serial.println();
}

void loop() {
  // This ensures CONTINUOUS reception
  
  if (!client.connected()) {
    reconnect();
  }
  
  // Must call loop() continuously to process incoming messages
  client.loop();
  
  // Print status every 30 seconds to show it's alive
  static unsigned long last_status = 0;
  if (millis() - last_status > 30000) {
    Serial.println();
    Serial.println("SYSTEM STATUS:");
    Serial.print("  Messages received: ");
    Serial.println(message_count);
    Serial.print("  Current movement: ");
    Serial.println(current_movement);
    Serial.print("  WiFi: ");
    Serial.println(WiFi.status() == WL_CONNECTED ? "Connected" : "Disconnected");
    Serial.print("  MQTT: ");
    Serial.println(client.connected() ? "Connected" : "Disconnected");
    Serial.println();
    last_status = millis();
  }
  
  delay(10); // Small delay to prevent watchdog timer
}
#include <WiFi.h>
#include <PubSubClient.h>
#include <WiFiClientSecure.h>

// === WiFi Credentials ===
const char* ssid = "iPhone";
const char* password = "zhuqshenw";

// === MQTT Configuration ===
const char* mqtt_broker = "172.20.10.6";  // Window's IP
const int mqtt_port = 8883;
const char* topic_processed_data = "robot/movement/class";

// === Root CA Certificate (for TLS) ===
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

// Certificate (fb2.crt)
const char* certificate = \
"-----BEGIN CERTIFICATE-----\n" \
"MIIDCTCCAfECFFkD43rhcXzS6nQFNMARfDGBbpzAMA0GCSqGSIb3DQEBCwUAMGQx\n" \
"CzAJBgNVBAYTAlNHMQswCQYDVQQIDAJTRzEMMAoGA1UECgwDTlVTMRcwFQYDVQQD\n" \
"DA5NUVRUIENBIFNlcnZlcjEhMB8GCSqGSIb3DQEJARYSZTA5NjgxMTZAdS5udXMu\n" \
"ZWR1MB4XDTI1MTAwNzEyNTk0N1oXDTI1MTEwNjEyNTk0N1owHjEcMBoGA1UEAwwT\n" \
"dW5pdHktbW9iaWxlLWNsaWVudDCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoC\n" \
"ggEBAIzU+bGkPeU89KQVkINZCMv4iRQP9yCqdYqExFFCJhBC3xnnTOQBvOfOz01E\n" \
"pXXHgD1FhHCxHup/sgOBKp2hRLynzxxDuRYME3Wc/S9lvzhfAHJGnOByRb8I0B5v\n" \
"T9ufwy9ExN+ZV/EwYxt2gdTscyPnoKzS/ro1vUUeWAoPcO6dnD0pDoyKpIjfMAwP\n" \
"8XNujKmQ6TT63GXkOauFHNNnKG5hpl9IMlQtNA89UwEwD333cv7aKHmm/QtWvVC4\n" \
"/6KgCWA9mHPbfCsS33cyDxHu4ZIVxGiQb6CZ8tg9Zf/slDVba8hKSNRGuMaOmu+E\n" \
"h5/rAC9bnVHVs/oxgELAIqJ1O20CAwEAATANBgkqhkiG9w0BAQsFAAOCAQEAE3OG\n" \
"nzWErIVZKcxYzcqdEJ0jikH0BRtORl17VJpLJDe/a1+6AW643TjzTveEzdTTj/AH\n" \
"d8vr1Iffj4hqf27IheXlBbwzWFejcSysuP1rjdf9DF/zWFzLvhJnfd1yhTQepIY6\n" \
"eyl8nRV0aIQ9EMK+W9i5TBlfn47vvS1dvwFk6FmKfLHBAu4il056YwkK2MCJO58Z\n" \
"ZvictJ4p+pteEQZP3Fj2EXTEv8dyT0uX1mCXxJGLlvB36Fzzmo4OOlTWPpCOHMLq\n" \
"cZh6zZLmMGZQDaKCUB6hwHyZA8WRuT9s7vqpGzUPbBU7fjp36JU0hxg0D+RJaPhE\n" \
"EMMYTN9WarJBddlBEA==\n" \
"-----END CERTIFICATE-----\n";

// Private Key (fb2(client).key)
const char* private_key = \
"-----BEGIN PRIVATE KEY-----\n" \
"MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQCM1PmxpD3lPPSk\n" \
"FZCDWQjL+IkUD/cgqnWKhMRRQiYQQt8Z50zkAbznzs9NRKV1x4A9RYRwsR7qf7ID\n" \
"gSqdoUS8p88cQ7kWDBN1nP0vZb84XwByRpzgckW/CNAeb0/bn8MvRMTfmVfxMGMb\n" \
"doHU7HMj56Cs0v66Nb1FHlgKD3DunZw9KQ6MiqSI3zAMD/FzboypkOk0+txl5Dmr\n" \
"hRzTZyhuYaZfSDJULTQPPVMBMA9993L+2ih5pv0LVr1QuP+ioAlgPZhz23wrEt93\n" \
"Mg8R7uGSFcRokG+gmfLYPWX/7JQ1W2vISkjURrjGjprvhIef6wAvW51R1bP6MYBC\n" \
"wCKidTttAgMBAAECggEABZ4BD5rTdS9HOrw5dWO5vBj/rrMsUjs6UPoWsn8G8aMZ\n" \
"LvlQ0c9X748KKbTRPK9maAs7yxrldsj9GrKuNndWPIgc9K2m1kBJDmnil19hjygK\n" \
"5oP2geVM7t+1HWGnN8VZjasahyign1gku9WwPAPqW8ZDXGFWE6tND1K0hEI1aO8F\n" \
"Q0XhIzQsPQGiyKilBElEBDmbAkQbKh4WIbnBPhUOZhHWnpYg0gsCEMl4NGfObbYT\n" \
"GsNm7RFtGvN2yk4qWvgOGelIMiJgjDVzfuGuCCmX/XnBYlrlhVP4o+CAz9OJWVtm\n" \
"gkdwtT/0T/ATVeuWffO0L4XBNZi52vy3iyKHUyALQQKBgQDDF5myzhV+IekS83P/\n" \
"wb/y1vNYj9uS01KZpgXsfFnNJb2hpFXqHbYcf1Xg9+lCA5DjQvZnO/E8Xw2Tt/cG\n" \
"tSlfrZ2XdRgjroRlFHbdMBGrsrP9yaSW0QvJcYGubglR3mHPSTqBtE6DFby+2j5h\n" \
"s2pF3mmLVyXiILhZZe2nb29gGQKBgQC4zLhBMhZngsl56K1ofrqE6iged2As9C9G\n" \
"VQfPZrFAVup2rx7/h2AqMI/Lj3ICBKJq1CCzSdG+rWe+SI3OgkiHbJCFEVB//p0A\n" \
"U7ro1rx8R84BwyEioZN0CsJPI8aMGDlIG8Lml5SOO9ktkJSmp4m5aaF/JDecNavU\n" \
"ap+00YrQdQKBgQC5y6oWvWl+nDDqWWypsA1r6gYK28ZTSGor5g9SLwMe+shkPquL\n" \
"sQwUi7hv7en5cofzx3v+yPlvc17sxZC+lJ14f1HMQjnhEX0I/rpM4FCT4jbEhdr3\n" \
"vtKo4C6OvkCl9VHVJXpQuDTlZjhA0nwCc+nL7Is7pp1vg5XNneL9SIUbUQKBgGvR\n" \
"JP8ElgW2TI4Prnx006WQZ+++fiI8JQjHu1LJ+0gqbYjpCxDSjsyOoJaHDmEXCxuA\n" \
"v8NaokC5MvnVosaFRIOeV4MLYwgKKNd0AmyuPDHWQt7MVZy64Cinzk4V9VTvHRxw\n" \
"9flLHqUNTdxDqjbBMJ04f7yKCNfeiG3Z92urhW2xAoGALWTLUH6/w8SGqIXRcDmK\n" \
"NcxuJmAzkaGzHpGa0JwbCtuYXcg1Nijdc1PozU2X+dkde3b+5M6RUhHz5DnQXYWD\n" \
"p/HaJFLvBgAyBeMQ0nA5IZy6kJC3JVPk7aGq3Sq0XBPVh5RCp7GM9mYrshvEsa7+\n" \
"Hkk97i+n6hTXNNb2IYfayhw=\n" \
"-----END PRIVATE KEY-----\n";

// === MQTT + WiFi clients ===
WiFiClientSecure espClient;
PubSubClient client(espClient);

// === Motor Pins ===
#define LEFT_IN1 27
#define LEFT_IN2 26
#define RIGHT_IN1 13
#define RIGHT_IN2 5

// === MQTT Commands ===
const char* movement_classes[] = {"STOP", "COME_HERE", "GO_AWAY", "TURN_AROUND", "PET", "FEED"};
int current_movement = 0;
int message_count = 0;

// === WiFi Setup ===
void setup_wifi() {
  Serial.begin(115200);
  Serial.println("\nConnecting to WiFi...");
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n✅ WiFi connected");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

// === Motor Control ===
void stopMotors() {
  digitalWrite(LEFT_IN1, LOW);
  digitalWrite(LEFT_IN2, LOW);
  digitalWrite(RIGHT_IN1, LOW);
  digitalWrite(RIGHT_IN2, LOW);
}

void moveForwardShort() {
  digitalWrite(LEFT_IN1, HIGH); digitalWrite(LEFT_IN2, LOW);
  digitalWrite(RIGHT_IN1, HIGH); digitalWrite(RIGHT_IN2, LOW);
  delay(500);
  stopMotors();
}

void moveBackwardShort() {
  digitalWrite(LEFT_IN1, LOW); digitalWrite(LEFT_IN2, HIGH);
  digitalWrite(RIGHT_IN1, LOW); digitalWrite(RIGHT_IN2, HIGH);
  delay(500);
  stopMotors();
}

void turnAround() {
  digitalWrite(LEFT_IN1, HIGH); digitalWrite(LEFT_IN2, LOW);
  digitalWrite(RIGHT_IN1, LOW); digitalWrite(RIGHT_IN2, HIGH);
  delay(700);
  stopMotors();
}

void petAction() {
  for (int i = 0; i < 3; i++) {
    moveForwardShort();
    delay(100);
    moveBackwardShort();
    delay(100);
  }
}

void feedAction() {
  moveForwardShort();
}

// === Execute Command ===
void executeMovement(int movement) {
  switch (movement) {
    case 0: stopMotors(); break;                    // STOP
    case 1: moveForwardShort(); break;              // COME HERE
    case 2: moveBackwardShort(); break;             // GO AWAY
    case 3: turnAround(); break;                    // TURN AROUND
    case 4: petAction(); break;                     // PET
    case 5: feedAction(); break;                    // FEED
  }
}
// === MQTT Callback ===
void callback(char* topic, byte* payload, unsigned int length) {
  String message = "";
  for (int i = 0; i < length; i++) message += (char)payload[i];
  message_count++;

  Serial.print("[" + String(message_count) + "] Received: ");
  Serial.println(message);

  int movement = message.toInt();
  if (movement >= 0 && movement <= 5) {
    current_movement = movement;
    Serial.print("Executing: ");
    Serial.println(movement_classes[movement]);
    executeMovement(movement);
  } else {
    Serial.println("Invalid movement command.");
  }
}

// === MQTT Reconnect ===
void reconnect() {
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection... ");
    String clientId = "FireBeetle-";
    clientId += String(random(0xffff), HEX);
    
    if (client.connect(clientId.c_str())) {
      Serial.println("Connected to MQTT broker!");
      if (client.subscribe(topic_processed_data)) {
        Serial.print("Subscribed to: ");
        Serial.println(topic_processed_data);
      } else {
        Serial.println("Subscription failed!");
      }
    } else {
      Serial.print("Failed, rc=");
      Serial.print(client.state());
      Serial.println(" - retrying in 5s");
      delay(5000);
    }
  }
}

// === Setup ===
void setup() {
  setup_wifi();

  // Motor setup
  pinMode(LEFT_IN1, OUTPUT);
  pinMode(LEFT_IN2, OUTPUT);
  pinMode(RIGHT_IN1, OUTPUT);
  pinMode(RIGHT_IN2, OUTPUT);
  stopMotors();

  // TLS + MQTT
  espClient.setCACert(ca_cert);
  espClient.setCertificate(certificate);
  espClient.setPrivateKey(private_key);

  client.setServer(mqtt_broker, mqtt_port);
  client.setCallback(callback);
  client.setKeepAlive(60);

  reconnect();
  Serial.println("FireBeetle Robot Ready for Commands");
}

// === Main Loop ===
void loop() {
  if (!client.connected()) reconnect();
  client.loop();
  delay(10);
}
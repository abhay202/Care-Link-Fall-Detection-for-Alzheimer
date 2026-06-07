#include <Wire.h>
#include "MAX30105.h"
#include "heartRate.h"

MAX30105 particleSensor;

const byte RATE_SIZE = 8; // Increased for better averaging
byte rates[RATE_SIZE];
byte rateSpot = 0;
long lastBeat = 0;

float beatsPerMinute;
int beatAvg;

// Stabilization variables
const int BUFFER_SIZE = 10;
int bpmBuffer[BUFFER_SIZE];
int bufferIndex = 0;
int stabilizedBPM = 0;
int minBPM = 40;
int maxBPM = 200;

unsigned long lastSendTime = 0;
const int SEND_INTERVAL = 6.66; 

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\nMAX30102 Heart Rate Sensor Test");
  
  // Initialize I2C
  Wire.begin();
  
  // Initialize sensor
  if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) {
    Serial.println("MAX30102 was not found. Please check wiring/power.");
    while (1);
  }
  
  Serial.println("MAX30102 initialized");
  
  // Configure sensor
  particleSensor.setup();
  particleSensor.setPulseAmplitudeRed(0x0A);
  particleSensor.setPulseAmplitudeGreen(0);
  particleSensor.setPulseAmplitudeIR(0x33);
}

void loop() {
  long irValue = particleSensor.getIR();
  
  // Detect finger
  if (checkForBeat(irValue) == true) {
    long delta = millis() - lastBeat;
    lastBeat = millis();
    
    beatsPerMinute = 60 / (delta / 1000.0);
    
    if (beatsPerMinute < 255 && beatsPerMinute > 20) {
      rates[rateSpot++] = (byte)beatsPerMinute;
      rateSpot %= RATE_SIZE;
      
      beatAvg = 0;
      for (byte x = 0; x < RATE_SIZE; x++)
        beatAvg += rates[x];
      beatAvg /= RATE_SIZE;
      
      // Add to stabilization buffer
      addToBuffer(beatAvg);
    }
  }
  
  // Timed Sending - Just stabilized BPM value
  unsigned long now = millis();
  if (now - lastSendTime >= SEND_INTERVAL) {
    Serial.println(stabilizedBPM);
    lastSendTime = now;
  }
}

void addToBuffer(int bpmValue) {
  // Outlier rejection - ignore spikes
  if (bufferIndex > 0) {
    int lastValue = bpmBuffer[(bufferIndex - 1 + BUFFER_SIZE) % BUFFER_SIZE];
    if (abs(bpmValue - lastValue) > 30) {
      return; 
    }
  }
  
  bpmBuffer[bufferIndex] = bpmValue;
  bufferIndex = (bufferIndex + 1) % BUFFER_SIZE;
  
  // Calculate median for better stability
  stabilizedBPM = getMedian();
}

int getMedian() {
  int temp[BUFFER_SIZE];
  for (int i = 0; i < BUFFER_SIZE; i++) {
    temp[i] = bpmBuffer[i];
  }
  
  // Simple sort
  for (int i = 0; i < BUFFER_SIZE - 1; i++) {
    for (int j = 0; j < BUFFER_SIZE - i - 1; j++) {
      if (temp[j] > temp[j + 1]) {
        int swap = temp[j];
        temp[j] = temp[j + 1];
        temp[j + 1] = swap;
      }
    }
  }
  
  // Return middle value
  return temp[BUFFER_SIZE / 2];
}
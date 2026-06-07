#include <Arduino.h>
#include <Wire.h>
#include <MAX3010x.h>
#include "filter.h" // Assumed library for filter classes: LowPassFilter, HighPassFilter, Differentiator, MovingAverageFilter, MinMaxAvgStatistic

MAX30105 sensor;

// Track if the sensor is actually connected
bool sensor_online = false;

// ----- Sensor & Filter Constants -----
static const auto        kSamplingRate         = MAX30105::SAMPLING_RATE_100SPS;
static const float       kSamplingFrequency    = 100.0f;

static const float kLowPassCutoff          = 5.0f;  // PPG Low-Pass (smoothing pulse)
static const float kHighPassCutoff         = 0.5f;  // PPG High-Pass (removing DC baseline)

// ----- PPG / Finger detection constants -----
static const unsigned long kFingerThreshold    = 3000;  
static const unsigned int  kFingerCooldownMs   = 500;   
static const float         kEdgeThreshold      = -2000.0f; // Baseline differential threshold
static const float         kBeatPeakThreshold  = 0.5f;     // Dynamic threshold fraction (50% of peak rise)

// ----- BPM Averaging Constants -----
static const bool kEnableAveraging         = true;
static const int  kAveragingSamples        = 5;
static const int  kSampleThreshold         = 2;


// ----- Filter and Statistic Objects -----
LowPassFilter low_pass_filter_red(kLowPassCutoff, kSamplingFrequency);
HighPassFilter high_pass_filter(kHighPassCutoff, kSamplingFrequency);
Differentiator differentiator(kSamplingFrequency);

MovingAverageFilter<kAveragingSamples> averager_bpm;
MinMaxAvgStatistic stat_red;

// ----- State Variables -----
unsigned long last_heartbeat      = 0;
unsigned long finger_timestamp    = 0;
bool          finger_detected     = false;

float         last_diff           = NAN;
bool          crossed             = false;
unsigned long crossed_time        = 0;
float         max_diff_in_cycle   = NAN; 

// Zero-BPM printing
unsigned long last_zero_print_ms      = 0;
const unsigned long kZeroPrintIntervalMs = 1000;


// -------------------------------------------------------------------

void resetProcessingState() {
  differentiator.reset();
  averager_bpm.reset();
  low_pass_filter_red.reset();
  high_pass_filter.reset();
  // ...existing code...
  stat_red.reset();
  last_diff = NAN;
  crossed   = false;
  max_diff_in_cycle = NAN; 
}

void setup() {
  Serial.begin(115200);
  delay(100); 
  Wire.begin();

  if (!sensor.begin()) {
    Serial.println(F("MAX3010x not found. Running in SOUND-ONLY mode."));
    sensor_online = false;
  } else {
    sensor_online = true;
    sensor.setSamplingRate(kSamplingRate);
    Serial.println(F("Sensor Found. Place your finger to start..."));
  }
}

void loop() {
  unsigned long now_ms = millis();
  
  // ...existing code...


  // ============================================================
  // SCENARIO 1: SENSOR IS MISSING / BROKEN
  // ============================================================
  if (!sensor_online) {
    // Print BPM=0 periodically
    if (now_ms - last_zero_print_ms > kZeroPrintIntervalMs) {
      Serial.print("BPM=");
      Serial.println(0);
      last_zero_print_ms = now_ms;  
    }
    return; // Skip the rest of the loop
  }

  // ============================================================
  // SCENARIO 2: SENSOR IS WORKING (Normal Logic)
  // ============================================================
  
  // ...existing code...
  
  auto sample = sensor.readSample(20); 

  if (sample.red == 0 && sample.ir == 0) {
    return;
  }

  // Check Finger Logic
  if (sample.red > kFingerThreshold) { 
    if (!finger_detected && (now_ms - finger_timestamp > kFingerCooldownMs)) {
      finger_detected = true;
      resetProcessingState();
    }
  } else {
    if (finger_detected) {
      finger_detected = false;
      resetProcessingState();
      finger_timestamp = now_ms;
    }
  }

  // If Finger is Detected -> Calculate BPM
  if (finger_detected) {
    
    // BPM Calculation
    float current_value_red = (float)sample.red;

    current_value_red = low_pass_filter_red.process(current_value_red);
    stat_red.process(current_value_red);

    float hp            = high_pass_filter.process(current_value_red);
    float current_diff  = differentiator.process(hp);

    if (!isnan(current_diff) && !isnan(last_diff)) {
      
      // 1. Track the maximum positive derivative (peak of the pulse rise)
      if (current_diff > max_diff_in_cycle || isnan(max_diff_in_cycle)) {
          max_diff_in_cycle = current_diff;
      }

      // 2. Check for zero-crossing (Positive to Negative)
      if (last_diff > 0 && current_diff < 0) {
        crossed = true;
        crossed_time = now_ms;
      }
      
      // 3. Beat Detection: Check for the characteristic negative peak
      if (crossed && max_diff_in_cycle > 0) {
          float dynamic_threshold = -max_diff_in_cycle * kBeatPeakThreshold;

          if (current_diff < kEdgeThreshold || current_diff < dynamic_threshold) {
             
            unsigned long beat_time = crossed_time;
            if (last_heartbeat != 0 && (beat_time - last_heartbeat) > 300) {
              int bpm = (int)(60000UL / (beat_time - last_heartbeat));

              if (bpm > 50 && bpm < 250) {
                if (kEnableAveraging) {
                  int avg_bpm = averager_bpm.process(bpm);
                  if (averager_bpm.count() >= kSampleThreshold) {
                    Serial.print("BPM=");
                    Serial.println(avg_bpm); 
                  }
                } else {
                  Serial.print("BPM=");
                  Serial.println(bpm); 
                }
              }
              stat_red.reset(); 
            }
            // Reset for the next cycle
            crossed           = false;
            last_heartbeat    = beat_time;
            max_diff_in_cycle = NAN; 
          }
      }
    }
    last_diff = current_diff;
  
  } else {
    // No Finger Detected (but sensor works) -> Print BPM=0
    if (now_ms - last_zero_print_ms > kZeroPrintIntervalMs) {
      Serial.print("BPM=");
      Serial.println(0);
      last_zero_print_ms = now_ms;  
    }
  }
}
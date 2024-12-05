/* APS380 CAS Project Code
   Last Modified: by Ziming MA
   date: 2024-12-04
   version: v0.5.3
   description: Bluetooth control / just run + testing for final report
   history: v0.1: Ziming MA     : basic control
            v0.2: Ziming MA     : motor speed sensing & control
            v0.3: Ahmad Kaleem  : TF-Luna Lidar INterface & CAS v1
            v0.4: Ziming MA     : CAS v2 & ABS
*/
// "l: infor ... "
// "v: 11"
// "i: 1.1"
// ==================== Library Include ====================
#include <arduino-timer.h>
#include <Wire.h>    // Instantiate the Wire library
#include <TFLI2C.h>  // TFLuna-I2C Library v.0.1.1
#include <SoftwareSerial.h>
#include <math.h>

// ==================== Pin Defination ====================
// motor driver
#define motor_left    2
#define motor_left_1  3
#define motor_right   8
#define motor_right_1 9
// motor speed sensor
#define left_tach 19
#define right_tach 18
// motor speed sensor
#define rx_bluetooth 50
#define tx_bluetooth 21

// ==================== Constants Defination ====================
#define max_speed_left 250
#define max_speed_right 225
#define CAS_trigger_distance 50

// ==================== Global Variable Defination ====================
// distance sensor global variable
TFLI2C tflI2C;

int16_t tfDist;                // distance in centimeters
int16_t tfAddr = TFL_DEF_ADR;  // Use this default I2C address

// speed sensor global variable
auto timer = timer_create_default();  // create a timer with default settings

int counter_left = 0;
int counter_right = 0;

// other global variable
char command;
// SoftwareSerial BluetoothControl(rx_bluetooth, tx_bluetooth);
SoftwareSerial BluetoothControl(52, 53);
bool CAS_ABS = true;
bool ABS_active = false;

int min_distance_detected = 1000;
float speed_limiting_factor = 0.0;
int speed_left_lim = max_speed_left;
int speed_right_lim = max_speed_right;

int state = 0;  // to keep track which state car is in currently.
/* 
  1: forward
  -2: backward
  3: rotate left
  4: rotate right
  8: forward full speed
  0: stop
  -1: CAS triggered
*/

// ==================== Helper Functions ====================
float get_speed_limiting_factor (int distance) {
  if (distance < 100) {
    return 0.2;
  } else if (distance < 500) {
    return (0.6 / 400) * (distance - 100) + 0.2;
  } else {
    return 1.0;
  }
}

void update_speed_limiting_factor () {
  speed_left_lim = (int) (get_speed_limiting_factor(min_distance_detected) * max_speed_left);
  speed_right_lim = (int) (get_speed_limiting_factor(min_distance_detected) * max_speed_right);
  
  BluetoothControl.println("l:dist = " + String(min_distance_detected));
  BluetoothControl.println("l:lim_factor = " + String(get_speed_limiting_factor(min_distance_detected)));
  BluetoothControl.println("l:speed_left_lim = " + String(speed_left_lim));
  BluetoothControl.println("l:speed_right_lim = " + String(speed_right_lim));
  Serial.println("l:dist = " + String(min_distance_detected));
  Serial.println("l:lim_factor = " + String(get_speed_limiting_factor(min_distance_detected)));
  Serial.println("l:speed_left_lim = " + String(speed_left_lim));
  Serial.println("l:speed_right_lim = " + String(speed_right_lim));
  
}

void forward_left(int speed) {
  analogWrite(motor_left, speed);
  digitalWrite(motor_left_1, LOW);
}

void forward_right(int speed) {
  analogWrite(motor_right, speed);
  digitalWrite(motor_right_1, LOW);
}

void backward_left(int speed) {
  analogWrite(motor_left, 255 - speed);
  digitalWrite(motor_left_1, HIGH);
}

void backward_right(int speed) {
  analogWrite(motor_right, 255 - speed);
  digitalWrite(motor_right_1, HIGH);
}

void stop() {
  digitalWrite(motor_left, LOW);
  digitalWrite(motor_left_1, LOW);
  digitalWrite(motor_right, LOW);
  digitalWrite(motor_right_1, LOW);
  // Serial.println("stopped");
}

void ABS() {
  ABS_active = true;
  Serial.println("ABS start");
  // stop();
  // moving direction
  int direction = 1;
  if (state < 0) {
    direction = -1;
  }
  int counter_now = counter_left + counter_right;  // current total counter value
  int counter_pre = counter_now - 100;             // previous total counter value
  int counter_diff = 100;                          // difference in total counter value for rotation speed estimation
  int counter_diff_pre = 200;                      // difference in total counter value for rotation speed estimation
  int counter_stop = 0;                            // number of countinous low speed iterations detected
  while (counter_stop < 10) {                      // if low speed for over 10 period, exit the loop
    counter_now = counter_left + counter_right;    // update counter values
    counter_diff = counter_now - counter_pre;      // estimate speed
    Serial.println(counter_now);
    Serial.println(counter_diff);
    // check estimated speed
    if (counter_diff < 3) {
      // this iteration is low speed, low torque braking applied
      stop();
      Serial.println("low speed");
      counter_stop++;
    } 
    else if ((counter_diff_pre - counter_diff) < -1) {
      // positive acceleration detected => wrong firection assumption => flip torque direction
      stop();
      Serial.println("postive acceleration detected");
    }
    else {
      // this iteration is high speed, high torque braking applied
      if (direction == 1) {  // moving forward, apply negtive torque
        Serial.println("negtive torque");
        digitalWrite(motor_left, LOW);
        digitalWrite(motor_left_1, HIGH);
        digitalWrite(motor_right, LOW);
        digitalWrite(motor_right_1, HIGH);
      } else if (direction == -1) {  // moving backward, apply negtive torque
        Serial.println("positive torque");
        digitalWrite(motor_left, HIGH);
        digitalWrite(motor_left_1, LOW);
        digitalWrite(motor_right, HIGH);
        digitalWrite(motor_right_1, LOW);
      }
    }
    // wait for 10ms then go to next iteration
    counter_diff_pre = counter_diff;
    counter_pre = counter_now;
    delay(10);
  }
  stop();
  Serial.println("ABS stopped");
  ABS_active = false;
}

// ==================== Handler Functions  ====================
// interrupt handllers
void handler_count_left() {
  // Serial.println("counter_left++");
  counter_left++;
}

void handler_count_right() {
  // Serial.println("counter_right++");
  counter_right++;
}

void send_data_to_plot_1s() {
  if (!ABS_active) {
    // Serial.println("motor speed:");
    // 20 holes on the disk
    // Serial.println(counter_left / 20 * 60);
    // Serial.println(counter_right / 20 * 60);
    BluetoothControl.println("s:" + String(counter_left + counter_right / 20 * 60 / 2));
    // Serial.println("s:" + String(counter_left + counter_right / 20 * 60 / 2));
    BluetoothControl.println("l:s," + String(counter_left + counter_right / 20 * 60 / 2));
    BluetoothControl.println("l:d," + String(min_distance_detected));
    counter_left = 0;
    counter_right = 0;
  }
}

// serial control handllers
void serial_handler() {
  switch (command) {
    case ' ':  // stop.
      state = 0;
      stop();
      // Serial.println("stop");
      // BluetoothControl.println("l:stop");
      break;
    case 't':  // stop.
      state = 0;
      stop();
      Serial.println("stop");
      BluetoothControl.println("l:stop");
      break;
    case 'w':  // forward
      state = 1;
      forward_left(max_speed_left);
      forward_right(max_speed_right);
      Serial.println("forward");
      BluetoothControl.println("l:forward");
      break;
    case 's':  // backward
      state = -2;
      backward_left(max_speed_left);
      backward_right(max_speed_right);
      Serial.println("backward");
      BluetoothControl.println("l:backward");
      break;
    case 'a':  // rotate left
      state = 3;
      backward_left(max_speed_left);
      forward_right(max_speed_right);
      Serial.println("left");
      BluetoothControl.println("l:left");
      break;
    case 'd':  // rotate right
      state = 4;
      forward_left(max_speed_left);
      backward_right(max_speed_right);
      Serial.println("right");
      BluetoothControl.println("l:right");
      break;
    case 'q':  // full speed forward
      state = 8;
      update_speed_limiting_factor();
      forward_left(speed_left_lim);
      forward_right(speed_right_lim);
      //Serial.println("forward full speed");
      BluetoothControl.println("l:forward full speed");
      break;
    case 'e':  // flip CAS mode: ABS or Traditional
      CAS_ABS = ! CAS_ABS;
      Serial.print("ABS enabled for CAS: ");
      Serial.println(CAS_ABS);
      BluetoothControl.println("l:ABS enabled for CAS: " + String(CAS_ABS));
      break;
      /*
    default:
      stop();
      break;
    */
  }
}

// ==================== Arduino Setup  ====================
void setup() {
  // put your setup code here, to run once:
  pinMode(motor_left, OUTPUT);
  pinMode(motor_left_1, OUTPUT);
  //pinMode(4, OUTPUT);
  //pinMode(5, OUTPUT);  //bad
  //pinMode(6, OUTPUT);  //bad
  //pinMode(7, OUTPUT);  //bad
  pinMode(motor_right, OUTPUT);
  pinMode(motor_right_1, OUTPUT);
  Serial.begin(9600);
  BluetoothControl.begin(9600);
  stop();
  Wire.begin();  // Initalize Wire library
  attachInterrupt(digitalPinToInterrupt(left_tach), handler_count_left, RISING);
  attachInterrupt(digitalPinToInterrupt(right_tach), handler_count_right, RISING);
  timer.every(1000, send_data_to_plot_1s);
  timer.every(100, serial_handler);
  delay(2000);
  Serial.println("initialized");
  BluetoothControl.println("l:initialized");
  command = 'q';
  serial_handler();
}

// ==================== Arduino Main Loop  ====================
void loop() {
  // put your main code here, to run repeatedly:
  // CAS handle
  if (tflI2C.getData(tfDist, tfAddr)) {
    //Serial.println(String(tfDist)+" cm / " + String(tfDist/2.54)+" inches");
    min_distance_detected = tfDist;
    // Serial.println("s:" + String(min_distance_detected));  // measure the max valid distance
    if (tfDist < CAS_trigger_distance && state > 0) {
      Serial.println("Object detected - handling");
      BluetoothControl.println("l:Object detected - handling");
      command = ' ';
      state = -1;
      if (CAS_ABS){
        ABS();
         BluetoothControl.println("l:ABS CAS triggered");
      } else {
        BluetoothControl.println("l:non-ABS CAS triggered");
        stop();
      }
      Serial.println("Object detected - done");
      BluetoothControl.println("l:Object detected - done");
    }
  } else {
    min_distance_detected = 800;
  }
  // serial control handle
  if (Serial.available() > 0) {
    command = Serial.read();
    Serial.println("serial control: " + String(command));
    BluetoothControl.println("l:serial control: " + String(command));
    serial_handler();
  }
  if (BluetoothControl.available() > 0) {
    command = BluetoothControl.read();
    Serial.println("bluetooth received: " + String(command));
    BluetoothControl.println("l:Arduino received: " + String(command));
    serial_handler();
  }
  delay(1);
  timer.tick();  // tick the timer
}

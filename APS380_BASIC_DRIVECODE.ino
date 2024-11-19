void driveForward(float inches) {
    // Proportional gain for left and right motors
    float Kp_right = 1.0;
    float Kp_left = 1.0;

    // Gyroscope threshold for acceptable alignment
    const float threshold = 2.0; // Degrees

    // PWM limits
    const int MIN_PWM_RIGHT = 120;
    const int MAX_PWM_RIGHT = 210;
    const int MIN_PWM_LEFT = 140;
    const int MAX_PWM_LEFT = 210;

    // Calculate drive duration based on distance and estimated speed
    const float speedInchesPerSecond = 10.0; // Estimated speed in inches per second
    float drive_duration = inches / speedInchesPerSecond * 1000; // Convert to milliseconds

    // Read the initial roll value
    readGyroData(); // Get the current roll reading
    float initialRoll = roll;

    unsigned long start_time = millis();

    while (millis() - start_time < drive_duration) {
        // Read gyroscope data
        readGyroData();
        float currentRoll = roll;
        float error = currentRoll - initialRoll;

        // Apply threshold to avoid unnecessary small corrections
        if (abs(error) < threshold) {
            error = 0;
        }

        // Calculate PWM using proportional control
        int PWM_right = constrain(Kp_right * abs(error), MIN_PWM_RIGHT, MAX_PWM_RIGHT);
        int PWM_left = constrain(Kp_left * abs(error), MIN_PWM_LEFT, MAX_PWM_LEFT);

        // Drive motors with calculated PWM values
        digitalWrite(in1, HIGH);
        digitalWrite(in2, LOW);
        analogWrite(enA, PWM_right); // Adjusted speed for right motor
        digitalWrite(in3, HIGH);
        digitalWrite(in4, LOW);
        analogWrite(enB, PWM_left);  // Adjusted speed for left motor

        delay(10); // Small delay for stability
    }

    // Stop the motors after reaching the target distance
    analogWrite(enA, 0);
    analogWrite(enB, 0);
    digitalWrite(in1, LOW);
    digitalWrite(in2, LOW);
    digitalWrite(in3, LOW);
    digitalWrite(in4, LOW);
}


void setup() {
  // put your setup code here, to run once:

}

void loop() {
  // put your main code here, to run repeatedly:

}

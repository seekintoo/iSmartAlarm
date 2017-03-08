byte switchPin = 8;
byte inByte = 0;

void setup() {
  Serial.begin(9600);
  while (!Serial) {
    ;
  }
  
  pinMode(switchPin, OUTPUT);
  digitalWrite(switchPin, LOW);
}

void loop() {
  if (Serial.available() > 0) {
    // get the new byte:
    inByte = Serial.read();
    
    if (inByte == 49 ) {
//    Serial.print(inByte, DEC);
      
      for (int i=0; i<2; ++i) {
        digitalWrite(switchPin, HIGH);
        delay(250);
        digitalWrite(switchPin, LOW);
        delay(250);
      }
      inByte = 0;
    }
  }
}

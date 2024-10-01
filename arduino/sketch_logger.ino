#include <WebServer.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <secrets.h>
#include <DHT.h>

#define DHTPIN 3     // what pin we're connected to
#define DHTTYPE DHT22   // DHT22
DHT dht(DHTPIN, DHTTYPE); // Initialize DHT sensor for normal 16mhz Arduino

//set up to connect to an existing network (e.g. mobile hotspot from laptop that will run the python code)
// const char* ssid = SECRET_SSID;
// const char* password = SECRET_PASS;
WiFiUDP Udp;
unsigned int localUdpPort = 4210;  //  port to listen on
char incomingPacket[255];  // buffer for incoming packets

//measurement variables
float hum;  //Stores humidity value
float temp; //Stores temperature value
float i;
unsigned long time_begin;
unsigned long time_end;
const unsigned long loop_time = 5;
const unsigned long trans_time = 10;
const unsigned long day = 10; // 86400
unsigned long time1;
unsigned long time0;
String temps, hums, times, toSend;

//time variables
const char* ntpServer = "pool.ntp.org";
const long  gmtOffset_sec = -8 * 3600;
const int   daylightOffset_sec = 3600;
String send_time;


unsigned long sec() {
   static unsigned long secondCounter = 0;
   static unsigned long prevSecMillis = 0;
   if (millis() - prevSecMillis >= 1000) {
       prevSecMillis += 1000;
       secondCounter ++;
   }
   return secondCounter;
}


String returnLocalTime()
{
  time_t now;
  struct tm timeinfo;
  String timing = "";
  if(!getLocalTime(&timeinfo)){
    Serial.println("Failed to obtain time");
    return "No time";
  }

  timing += time(&now);
  char timeStringBuff[50];
  strftime(timeStringBuff, sizeof(timeStringBuff), "%Y%m%d %H:%M:%S", &timeinfo); 
  timing += " ";
  timing += timeStringBuff;
  return timing;
}


void setup()
{ 
  digitalWrite(LED_BUILTIN, LOW);   // turn the LED off by making the voltage LOW
  Serial.begin(115200);
  delay(2000);

  temps = String("Temps,");
  hums = String("Hums,");
  times = String("Times,");
  time0 = sec();


  //Initialize the DHT sensor
  dht.begin();
  pinMode(LED_BUILTIN, OUTPUT);
}


void loop()
{
  time_begin = sec();
  time1 = sec();
  time1 -= time0;
  times += time1;
  times += ",";

  //Read data and store it to variables hum and temp
  hum = dht.readHumidity();
  temp = dht.readTemperature();
  temps += temp;
  temps += ",";
  hums += hum;
  hums += ",";
  Serial.println(time1);
  Serial.println(temp);
  // Serial.println(temps.length());

  if (time1 > day) {
    digitalWrite(LED_BUILTIN, HIGH);  // turn the LED on (HIGH is the voltage level)
    // we recv one packet from the remote so we can know its IP and port
    if(WiFi.getSleep() == true) {
      WiFi.setSleep(false);
    }
    if (WiFi.status() != WL_CONNECTED) {
      WiFi.begin(ssid, password);
      Serial.println("");
    }

    // Wait for connection
    while (WiFi.status() != WL_CONNECTED) {
      delay(500);
      Serial.print(".");
      if (WiFi.status() == WL_CONNECTED) {
        Serial.println("Connected to wifi");
        Udp.begin(localUdpPort);
        Serial.printf("Now listening at IP %s, UDP port %d\n", WiFi.localIP().toString().c_str(), localUdpPort);
        configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);
      }
    }

    send_time = returnLocalTime();

    Udp.begin(localUdpPort);
    bool readPacket = false;
    bool read2Packet = false;
    long trans_begin = sec();
    while (sec() < trans_begin + trans_time) {
      int packetSize = Udp.parsePacket();
      if (packetSize){
        // receive incoming UDP packets
        Serial.printf("Received %d bytes from %s, port %d\n", packetSize, Udp.remoteIP().toString().c_str(), Udp.remotePort());
        int len = Udp.read(incomingPacket, 255);
        if (len > 0)
        {
          incomingPacket[len] = 0;
        }
        Serial.printf("UDP packet contents: %s\n", incomingPacket);
        readPacket = true;
      }

      if (readPacket) {
        toSend = send_time + ";" + temps + ";" + hums + ";" + times + ";";
        // Serial.println(toSend.length());
        // Serial.println(readPacket);
        Serial.println("Sending data");

        for (int j = 0; j <= 7; j++) {
          Udp.beginPacket(Udp.remoteIP(), Udp.remotePort());
          Udp.print(toSend.substring(j * 1000, (j + 1) * 1000));
          Udp.endPacket();
          delay(50);
        }

        bool read2Packet = false;
        i = 0.0;
        while (i < 100000.0) {
          i += 1.0;
          int packet2Size = Udp.parsePacket();
          if (packet2Size){
            // receive incoming UDP packets
            Serial.printf("Received %d bytes from %s, port %d\n", packet2Size, Udp.remoteIP().toString().c_str(), Udp.remotePort());
            int len = Udp.read(incomingPacket, 255);
            if (len > 0)
            {
              incomingPacket[len] = 0;
            }
            Serial.printf("UDP packet contents: %s\n", incomingPacket);
            if (String(incomingPacket) == "Received data") {
              read2Packet = true;
            }
          }

          if (read2Packet) {
            digitalWrite(LED_BUILTIN, LOW);   // turn the LED off by making the voltage LOW
            i = 100001.0;
            WiFi.disconnect(true);
            WiFi.mode(WIFI_OFF);
            Udp.stop();
            temps = "Temps,";
            hums = "Hums,";
            times = "Times,";
            time0 = sec();
            readPacket = false;
            break;
          }
        }
      }
    }
  }

  time_end = sec();
  while(sec() < time_begin + loop_time){
    delay(10);
  }
  Serial.println("");
}

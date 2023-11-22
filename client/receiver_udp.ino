#include "stdio.h"
#include "stdlib.h"
#include "string.h"
#include "time.h"
#include "WiFi.h"
#include "AsyncUDP.h"

const char * ssid
const char * password

const int ledPin = 2; 

const int multi_port = 1234;
const int uni_port = 1235;

IPAddress src_ip;

AsyncUDP udp1;
AsyncUDP udp2;

// sequence array & push method
int seq_ary[1000] = {0};
// 配列を全て0で初期化

int ary_size = 0;
int right = 0;
int duplicate_count = 0;
bool resend_flag = false;

int compareInt(const void* a, const void* b) {
    int aNum = *(int*)a;
    int bNum = *(int*)b;

    return aNum - bNum;
}

void processPacket(AsyncUDPPacket packet) {
    char recvd[packet.length()];
    memcpy(recvd, packet.data(), packet.length());

    char *data;
    int sequence = atoi(strtok(recvd, ":"));

    data = strtok(NULL, ":"); 

    if (strcmp(data, "done") == 0) {
        // Serial.println(packet.isMulticast() ? "recv 'done' on multicast" : "recv 'done' on unicast");
        
        int size = atoi(strtok(NULL, ":"));

        char loss[30] = "";
        sprintf(loss, "%d:", sequence);

        right = sequence;
        for (int counter=right-size; counter < right; counter++) {
          if ( seq_ary[counter] == 1 ) {
            strcat(loss, "0");
          } else {
            strcat(loss, "1");
          }
        }
      
        // マルチキャストの場合，ランダム秒待機
        if (packet.isMulticast()) {
          long waitTime = random(0, 50);
          delay(waitTime);
        }

        packet.printf("%s", loss); 
    }
    else if (strcmp(data, "resend") == 0) {
        resend_flag = true;

        packet.printf("ok"); 
    }
    else if (strcmp(data, "reset") == 0) {
        memset(seq_ary, 0, sizeof(seq_ary));

        packet.printf("%d", duplicate_count); 
        
        right = 0;
        duplicate_count = 0;
        resend_flag = false;
    }
    else {
        if (resend_flag && seq_ary[sequence] == 1) {
            duplicate_count++;
        }

        seq_ary[sequence] = 1;

        if ( resend_flag ) {
          char loss[30] = "";
          sprintf(loss, "%d:", sequence);

          if ( seq_ary[sequence] == 1 ) {
            strcat(loss, "0");
          } else {
            strcat(loss, "1");
          }

          // マルチキャストの場合，ランダム秒待機
          if (packet.isMulticast()) {
            long waitTime = random(0, 100);
            delay(waitTime);
          }

          packet.printf("%s", loss); 
        }
    }
}

void setup() {
    pinMode(ledPin, OUTPUT);

    Serial.begin(115200);
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);
    if (WiFi.waitForConnectResult() != WL_CONNECTED) {
        Serial.println("WiFi Failed");
        while(1) {
            delay(1000);
            Serial.println("Please Reboot ESP32...");
        }
    } else {
      Serial.println("connected!");
    }

    // 制御パケット("done"や"end"以外は，受信表示は出ない)
    if (udp1.listenMulticast(IPAddress(239,1,2,3), multi_port)) {
        Serial.print("Multicast Listening on IP: ");
        Serial.println(WiFi.localIP());
        udp1.onPacket(processPacket);  
    }

    if (udp2.listen(uni_port)) {    
        Serial.print("UDP Listening on IP: ");
        Serial.println(WiFi.localIP());
        udp2.onPacket(processPacket);
    }
}


void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    // WiFiに接続しているときだけLEDを点灯させる
    digitalWrite(ledPin, HIGH); // LEDを点灯させる
  } else {
    digitalWrite(ledPin, LOW);  // WiFiに接続していないときはLEDを消す
  }
}  

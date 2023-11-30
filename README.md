# NonDuppy　

複数台のクライアント(IoTデバイス)に対してデータを送信します．

マルチキャストとユニキャストを切り換えることによって主な目的である**重複パケット**の数を削減させつつ，転送時間を減少させます．

## ファイル概要
- server/sender_udp_multithread.py
  
送信側のプログラムです．

送信側は受信状況のフィードバックをもとにマルチキャストとユニキャストを切り換えパケットを送信します．

- client/receiver_udp
  
受信側のプログラムです．



- sendFile/sendingFile_750KB.txt

約750KBのテストデータです．1パケット1KBととすると750個分のパケットとなります．

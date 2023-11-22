import time
import socket
import threading
import numpy as np
import queue
import openpyxl

# 2 https://www.msn.com/ja-jp/news/opinion/%E7%8C%AB%E3%81%A3%E3%81%A6%E3%81%BB%E3%82%93%E3%81%A8%E3%81%A9%E3%81%93%E3%81%A7%E3%82%82%E5%AF%9D%E3%82%8B-%E3%81%BE%E3%81%95%E3%81%8B%E3%81%AE%E5%A0%B4%E6%89%80%E3%81%A7%E6%B0%97%E6%8C%81%E3%81%A1%E3%82%88%E3%81%95%E3%81%9D%E3%81%86%E3%81%AA%E5%AF%9D%E9%A1%94%E3%82%92%E8%A6%8B%E3%81%9B%E3%82%8B%E7%8C%AB%E3%81%AB%E5%8F%8D%E9%9F%BF/ar-AA1j8GNf?cvid=b6e11216c3b84b38bcec8992d3c7017a

# Excel Settings
UNDER = 102
ROUND = 5

excel_name = "dev_eval.xlsx"
excel_url = f'C:\\Users\\admin\\Desktop\\CDSL\\Lab\\excel\\{excel_name}'
book = openpyxl.load_workbook(excel_url)
sheet_name = "25m_multi" # 25.5
print("----------------------------")
print("excelName: ", excel_name)
print("sheetName: ", sheet_name)
print("----------------------------")
sheet = book[sheet_name]


IP_set = {
    "B": "192.168.2.104"
}

# B I 私物
IP_set = {
    "B": "192.168.2.102", 
    "C": "192.168.2.103",
    "D": "192.168.2.104",
    "E": "192.168.2.105",
    "F": "192.168.2.106",
    "G": "192.168.2.107",
    "H": "192.168.2.109",
    "I": "192.168.2.110",
    "J": "192.168.2.111",
    "K": "192.168.2.112",
}

# IP Setting
LOCALHOST = socket.gethostbyname(socket.gethostname())
MULTICAST_IP = "239.1.2.3"
MULTI_PORT = 1234
UNI_PORT = 1235

# Sending Setting
print("-----------※送信する度に変える※-------------")

RECIEVER_IPs = [ip for ip in IP_set.values()]
RECV_NUM = len(RECIEVER_IPs)

SEPARATE_SIZE = 1000
INIT_BATCH_SIZE = 1
MAX_BACTH_SIZE = 25
INIT_TIMEOUT = 5
# RATEの値によっては，タイムアウトが発生し，間に合わなかったACKが次のシーケンスで受信される可能性がある(recv()関数の挙動による)
TIMEOUT_RATE = 7
print("SEPARATE_SIZE: ", SEPARATE_SIZE, "INIT_BATCH_SIZE: ", INIT_BATCH_SIZE, "MAX_BACTH_SIZE: ", MAX_BACTH_SIZE, "INIT_TIMEOUT: ", INIT_TIMEOUT, "TIMEOUT_RATE: ", TIMEOUT_RATE)

print("-----------※送信する度に変える※-------------")


recv_status = [{"recv_id": ip, "message": ""} for ip in RECIEVER_IPs ]
resend_ip = {}
for ip in RECIEVER_IPs:
    resend_ip[ip] = 0
resend_cnt = 0
 
# threadingにおいて，ユニキャストとマルチキャストのRTTを区それぞれ保存するために用意する
# スレッドセーフにするためにqueue.Queueを用いる
RTTs = queue.Queue()
multi_RTTs = queue.Queue()
# マルチキャストの際に，何台から現時点で受信したかをカウントし，全ての受信が完了したら受信ループを抜ける
recv_counter = queue.Queue()
batch_stat = 0
len_chunks = 0
chunks = []


FILE_NAME = 'C:\\Users\\admin\\Desktop\\CDSL\\Lab\\python\\mudp\\sendFile\\binary_750k.txt'
with open(FILE_NAME, 'r') as f:
    read_data = f.read()
    chunks = [read_data[j:j+SEPARATE_SIZE] for j in range(0, len(read_data), SEPARATE_SIZE)]
    len_chunks = len(chunks)
    del read_data

# UDPソケットを作成
udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_sock.bind((LOCALHOST, MULTI_PORT))
udp_sock.settimeout(INIT_TIMEOUT)


def timeout_handler(e):
    print("timeout error: ", e)
    print("This program was interrupted")
    exit()

# タイムアウト時にパケットロスを記録できなかったIDの機器に対して，パケットロス情報を追記
def add_timeout_loss(counter):
    global recv_status, batch_stat

    for recv in recv_status:
        len_msg = len(recv["message"])

        if len_msg < counter:
            print(recv["recv_id"] + " a:" + str(len_msg) + " b: " + str(counter))
            recv["message"] += "1" * (counter - len_msg)
        
            if batch_stat != 2:
                batch_stat = 1

def record_packet_loss(res):
    # パケットロス処理
    recv_id, loss_seq = res

    # recv_idにマッチするオブジェクトを抽出 [{recv_id: 0, message: ""}]
    global recv_status
    filtered = list(filter(lambda x: x["recv_id"] == recv_id, recv_status))
    if len(filtered) == 0:
        print(f"# invalid recv_id: {recv_id}")
        print("# stop program...")
        exit()
    
    # recv_idに一致するオブジェクトのmessageにloss_seqを追記
    matched_reciever = filtered[0]
    matched_reciever["message"] += loss_seq

    return 

def calc_batch_size(batch_size, stat):
    if stat == 0:
        # MAX_BACTH_SIZEは，受信機のバッファが溢れない量にする
        return batch_size + 1 if batch_size < MAX_BACTH_SIZE else batch_size
        # return batch_size + 1
    elif stat == 1:
        return max(batch_size // 2, 1)
    else:
        return batch_size

# RTTsはqueue.Queueであることが前提であるため関数化
def calc_avg_RTT(RTTs):
    if not isinstance(RTTs, queue.Queue):
        print('# invalid RTTs. RTTs must be queue.Queue and not empty.')
        return 0.5 # 決め打ち

    qlist = list(RTTs.queue)
    qsize = len(qlist)
    if qsize == 0:
        print("0 devision error")
        return 0.5
    
    avg = sum(qlist) / qsize
    return avg

def recv_ack(ack_seq, rtt_start, ip_list, expected_ip = None, type='unicast', mode = 'init'):
    global batch_stat

    while True:
        try:
            res, addr = udp_sock.recvfrom(1024)
            rtt_end = time.perf_counter()

            ip = addr[0]
            seq, loss_seq = res.decode().split(":")
            # print(f'{[k for k, v in IP_set.items() if v == ip][0]}[{ip}] ' + f'{seq}:{loss_seq}')

            # 送信したシーケンス番号と一致しない場合は，無視する
            if int(seq) != ack_seq:
                print("# invalid seq")
                continue

            global recv_counter
            if ip in list(recv_counter.queue):
                continue

            # パケットロスの場合は，loss_seqに1が含まれる
            if len(loss_seq) == 0 or "1" in loss_seq:
                batch_stat = 1

            # ACKの再送は"init"の方で処理する
            if type == 'multicast':   
                if mode == 'init':
                    recv_counter.put(ip)
                    record_packet_loss((ip, loss_seq))

                    # 受信機全員分貰えたら終了 
                    global multi_RTTs, RECV_NUM
                    multi_RTTs.put(rtt_end - rtt_start)
                    
                    if recv_counter.qsize() >= RECV_NUM:
                        break

                if mode == 'resend':
                    if ip not in ip_list:
                        # break
                        continue

                    recv_counter.put(ip)
                    if recv_counter.qsize() >= len(ip_list):
                        break
        
            # なぜか，unicastでも複数台の受信機が返る場合があるので，無効なIPは無視する
            if type == 'unicast':
                if expected_ip != ip:
                    print("# invalid ip")
                    print(f"__expected_ip: [{expected_ip}] / received_ip: [{ip}]")
                    continue
            
                if mode == 'init':
                    recv_counter.put(ip)
                    record_packet_loss((ip, loss_seq))

                    global RTTs
                    RTTs.put(rtt_end - rtt_start)

                    break

                # 再送信の際は，record_packet_lossに記録はしない
                if mode == 'resend':
                    # もしACKを受け取ってもパケットロスしていたら，受信済みにカウントしない
                    if loss_seq == "0": 
                        recv_counter.put(ip)
                    break
                
        except Exception as e:
            # タイムアウト
            print("recv_ack error: ")  
            print("__" + str(e))
            batch_stat = 2 
            break
    return     


# 再送信の場合は，send_ackを介さない
def send_ack(ack_seq, type='unicast', mode ='init', ip_list = [], size = 0):
    if type == 'unicast':
        try: 
            # ip_listが空でない場合は，ACKの再送の意味
            if len(ip_list):
                for ip in ip_list:
                    rtt_start = time.perf_counter()
                    print("ack_resended: " + ip)
                    udp_sock.sendto(f"{ack_seq}:done:{size}\0".encode(), (ip, UNI_PORT))
                    recv_ack(ack_seq, rtt_start, ip_list, ip, type, mode)
            else:
                for ip in RECIEVER_IPs:
                    rtt_start = time.perf_counter()
                    udp_sock.sendto(f"{ack_seq}:done:{size}\0".encode(), (ip, UNI_PORT))
                    recv_ack(ack_seq, rtt_start, len(ip_list), ip, type, mode)

        except Exception as e:
            timeout_handler(e)
            pass

    elif(type == 'multicast'):
        rtt_start = time.perf_counter()
        try:
            udp_sock.sendto(f"{ack_seq}:done:{size}\0".encode(), (MULTICAST_IP, MULTI_PORT))
            
            respond_thread = threading.Thread(target=recv_ack(ack_seq, rtt_start, ip_list, None, type, mode))
            respond_thread.start()
            # スレッドが終了するまで待機
            respond_thread.join()
        except Exception as e:
            # timeout_handler(e)
            print(e)
            pass

    else:
        print('# chose incorrect type...')
        exit()


def finalize(timeout, mode = 'reset'):
    duplicate_cnt = {}
    udp_sock.settimeout(timeout)
    for ip in RECIEVER_IPs:
        while 1:
            try:
                if mode == 'reset':
                    udp_sock.sendto("0:reset\0".encode(), (ip, UNI_PORT))
                    while 1:
                        res, addr = udp_sock.recvfrom(1024)     

                        # reset時，重複パケット数が返る
                        if ":" in res.decode():
                            continue
                        
                        duplicate_cnt[addr[0]] = res.decode()
                        break
                elif mode == "resend":
                    udp_sock.sendto("0:resend\0".encode(), (ip, UNI_PORT))
                    res = udp_sock.recvfrom(1024)  
                else: 
                    print("__selected incorrect mode...")
                    exit()

                break
            except Exception as e:
                print("finalize error: ", ip)
                print(e)
                continue

    return duplicate_cnt

# chuncksをbatch_sizeづつ送信し，ackを受け取る
# mode = init: 初期送信, resend: 再送信
def send_batch():
    counter = 0  # counterの値をとるシーケンス番号のchunkは未送信
    batch_size = INIT_BATCH_SIZE
    border_chunks = 700
    RTT_avgs = []
    multi_RTT_avgs = []

    # ------送信処理------
    while counter < len_chunks:
        try:
            for i in range(batch_size):
                seq = counter + i
                chunk = str(seq) + ":" + chunks[seq] + "\0"
                udp_sock.sendto(chunk.encode(), (MULTICAST_IP, MULTI_PORT))

            counter += batch_size

            type = "multicast" if counter <= border_chunks else "unicast"
            send_ack(counter, type, "init", [], batch_size) # 0: 送信成功, 1: 送信成功(一部パケロス), 2: タイムアウト

            global recv_counter
            # 必要があればACKの再送
            while 1:
                if recv_counter.qsize() == RECV_NUM:
                    break

                ip_list = []
                for ip in RECIEVER_IPs:
                    if ip not in list(recv_counter.queue):
                        ip_list.append(ip)


                send_ack(counter, 'unicast', "init", ip_list, batch_size) # 0: 送信成功, 1: 送信成功(一部パケロス), 2: タイムアウト
   
        except Exception as e:
            print("error: ", e)
            print("This program was interrupted")
            exit()
    # ------送信処理------


        global RTTs, multi_RTTs, batch_stat
        latest_RTTs = 0
        latest_RTT_avgs = []
        # 直前に計測したRTTはユニキャストであるかマルチキャストであるかを判定
        if RTTs.qsize() > 0:   
            # print("ユニ遅延平均: ")
            latest_RTTs = RTTs
            latest_RTT_avgs = RTT_avgs
        if multi_RTTs.qsize() > 0:
            # print("マルチ遅延平均: ")
            latest_RTTs = multi_RTTs
            latest_RTT_avgs = multi_RTT_avgs


        avg = calc_avg_RTT(latest_RTTs)
        if avg > 0.0:
            udp_sock.settimeout(avg * TIMEOUT_RATE)
            latest_RTT_avgs.append(avg)

        add_timeout_loss(counter)
        
        batch_size = min(calc_batch_size(batch_size, batch_stat), len_chunks - counter)

        print("batch_size: ", batch_size, "batch_stat: ", batch_stat)


        # 初期化
        RTTs = queue.Queue()
        multi_RTTs = queue.Queue()
        batch_stat = 0
        recv_counter = queue.Queue()
    
    finalize(avg * TIMEOUT_RATE, "resend")

    # return RTT_avgs, multi_RTT_avgs
    return RTT_avgs, multi_RTT_avgs


# パケットひとつづつに応答確認を行う，
# 応答確認が無い場合は，再送信する
# 引数として，type(uni or multi)，再送が必要なパケットのシーケンス番号，再送が必要なクライアントのリスト
# ack_seqは，直近のパケットのシーケンス番号とする

def resend(seq, type, ip_list):
    global resend_cnt

    chunk = str(seq) + ":" + chunks[seq] + "\0"
    try:
        if type == 'unicast':
            for ip in ip_list:
                resend_cnt += 1
                udp_sock.sendto(chunk.encode(), (ip, MULTI_PORT))
                recv_ack(seq, 0, ip_list, ip, type, "resend")
                
        if type == 'multicast':
            resend_cnt += 1
            udp_sock.sendto(chunk.encode(), (MULTICAST_IP, MULTI_PORT))
            respond_thread = threading.Thread(target=recv_ack(seq, 0, ip_list, None, type, "resend"))
            respond_thread.start()
            # スレッドが終了するまで待機
            respond_thread.join()

    except Exception as e:
            print(e)
            print("resend error")
            exit()

def resend_check(common, standard_value, delay):
    udp_sock.settimeout(delay)
    global recv_counter
    global resend_ip
    seq = 0
    resend_list = []

    next = True
    while seq < len_chunks:
        # 送信する必要がない場合は，次のシーケンスへ

        common_seq = int(common[seq])
        # 再送の必要がないパケットはスルー
        if common_seq == 0:
            #if recv_counter.qsize() > 0:
            recv_counter = queue.Queue()
            seq += 1
            continue

        # 再送があり，かつ，受信機全員分のACKが返ってきている場合は，次の再送の受信者リストを更新
        if next:
            resend_list = []
            for recv in recv_status:
                if recv["message"][seq] == 1:
                    resend_list.append(recv["recv_id"])
        
        len_list = len(resend_list)
        print("resend require seq: " + str(seq))

        # 送信処理
        # if len_list > standard_value:
        #     resend(seq, 'multicast', resend_list)        
        # elif len_list <= standard_value:
        #     resend(seq, 'unicast', resend_list)   

        # resend(seq, 'unicast', resend_list)      
        resend(seq, 'multicast', resend_list)      

        
        # もし，再送信してもまだ受信できていない受信機がある場合は，再送信を続ける
        # print("受信数: " + str(recv_counter.qsize()) + " " + "再送台数: " + str(len_list))
        if recv_counter.qsize() < len_list:
            ip_l = []
            rc = list(recv_counter.queue)
            # もう一度再送を行う必要があるクライアントを求める
            for ip in resend_list:
                if ip not in rc:
                    ip_l.append(ip)
                resend_list = ip_l
            
            for ip in resend_list:
                resend_ip[ip] += 1

            next = False
            recv_counter = queue.Queue()
            continue

        next = True
        recv_counter = queue.Queue()
        seq += 1


# -------本処理--------
for t in range(UNDER, UNDER + ROUND):
    print("★~~~~~~~~~-------")
    print("start: " + str(t - UNDER + 1))
    start = time.perf_counter()

    # 各送信プロトコルでのRTTの平均を返り値として受け取る
    # RECIEVER_IPs, RECV_NUMが適切に設定されているかを確認
    RTT_avgs, multi_RTT_avgs = send_batch()

    start2 = time.perf_counter()
    end1 = start2 - start


    # 遅延を計算
    RTT_avgs = sum(RTT_avgs) / len(RTT_avgs)
    multi_RTT_avgs = sum(multi_RTT_avgs) / len(multi_RTT_avgs)

    print("Calculation Common...")

    common = np.zeros(len_chunks)
    for recv in recv_status:
        recv["message"] = list(map(int, recv["message"]))
        # なぜか各recv["message"]の要素数が異なっているため，共通度の計算が出来ない可能性がある
        common += np.array(recv["message"][:len_chunks])

    # 基準値を算出
    standard_value = 1
    # for i in range(2, RECV_NUM + 1):
    #     if multi_RTT_avgs >= RTT_avgs * i:
    #         standard_value = i   
    #     else: 
    #         break

    print("Uni delay: ", RTT_avgs)
    print("Multi delay: ", multi_RTT_avgs)
    print("standard_value: ", standard_value)

    print("-------Resend Check-------")
    resend_check(common, standard_value, multi_RTT_avgs * 3)

    end2 = time.perf_counter() - start2

    duplicate_cnt = finalize(multi_RTT_avgs * TIMEOUT_RATE, "reset")
    print(f"前半:{end1} 後半:{end2} 合計:{end1+end2}" )
    print("All Process Done")

    print("----------------------------")
    print(common)

    # Excelに書き込み
    cell = "B" + str(t)
    sheet[cell] = end1
    cell = "C" + str(t)
    sheet[cell] = end2
    cell = "D" + str(t)
    sheet[cell] = end1 + end2


    # 各受信機のパケットロスの内訳とパケットロス数を記録
    loop = 0
    sum_loss = 0
    for i, recv in enumerate(recv_status):
        ip = recv["recv_id"]
        message = recv["message"]

        cell = chr(ord("E")+loop) + str(t)
        sheet[cell] = ip + ":" + "".join(map(str, message))

        count = 0
        cell = chr(ord(cell[0])+1) + str(t)
        for p in message:
            if p == 1:
                count += 1

        try:
            d = int(duplicate_cnt[ip])
            r = int(resend_ip[ip])

            sheet[cell] =  str(count) + ":" + str(d) + ":" + str(r)
        except Exception as e:
            print("keyError: " + ip)
            sheet[cell] =  str(count) + ":error"

        loop += 2
        sum_loss += count
    
        cell = "AD" + str(t)
        sheet[cell] = resend_cnt



    cell = "Y" + str(t)
    sheet[cell] = RTT_avgs
    cell = "Z" + str(t)
    sheet[cell] = multi_RTT_avgs
    cell = "AA" + str(t)
    sheet[cell] = (", ".join(list(map(lambda x: str(int(x)), list(common)))))
    # sheet[cell] = "a"
    cell = "AB" + str(t)
    sheet[cell] = standard_value
    cell = "AC" + str(t)
    sheet[cell] = sum_loss

    recv_status = [{"recv_id": ip, "message": ""} for ip in RECIEVER_IPs ]
    udp_sock.settimeout(INIT_TIMEOUT)

    finalize(1,"reset")
    finalize(1,"reset")
    
    recv_status = [{"recv_id": ip, "message": ""} for ip in RECIEVER_IPs ]
    resend_ip = {}
    for ip in RECIEVER_IPs:
        resend_ip[ip] = 0
    resend_cnt = 0
    batch_stat = 0
    
    time.sleep(1.5)
    udp_sock.settimeout(INIT_TIMEOUT)

book.save(excel_url)


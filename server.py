#!/usr/bin/python
# -*- coding: UTF-8 -*-
# 文件名：server.py

import socket
import threading

import protocol


def send_data(sock, data):
    try:
        sock.send(data)
    except socket.error as e:
        print("ERROR: 发送失败，错误：%s" % e)


def send_message(sock, msg):
    print("send message: %s" % msg)
    try:
        sock.send(msg.encode('utf-8'))
    except socket.error as e:
        print("ERROR: 发送失败，错误：%s" % e)


# some reject case need to finish the socket connection
def thread_reject(sock, err_id):
    buf = b''
    while True:
        data, buf = protocol.extract_pack(buf)
        if len(data) > 0:
            break
        else:
            buf = buf + sock.recv(128)
    # the received message above should be client's join request, ignore it
    send_message(sock, protocol.server_reject_msg(err_id))
    sock.close()


def thread_receive_data(client_id):
    global team_size, shield_uid, accepting
    buf = b''
    while True:
        while True:
            data, buf = protocol.extract_pack(buf)
            if len(data) > 0:
                break
            else:
                buf = buf + sock_dict[client_id].recv(128)
        msg = data.decode('utf-8')
        print('receive from user %d: %s' % (client_id, msg))

        if msg.startswith(protocol.cmd_attack):
            turn_change_lock.acquire()  # lock turn
            turn_dict[client_id] += 1
            send_str = protocol.server_turn_msg(turn_dict)
            for sock in sock_dict.values():
                send_message(sock, send_str)
            turn_change_lock.release()  # unlock turn
            all_equal = True
            turn = turn_dict[client_id]
            for t in turn_dict.values():
                if t != turn:
                    all_equal = False
                    break
            if all_equal:  # send shield request
                while job_dict[shield_uid] != 1:
                    shield_uid += (shield_uid + 1) % team_size
                send_message(sock_dict[shield_uid], protocol.server_shield_msg(-1))
                shield_uid = (shield_uid + 1) % team_size

        elif msg.startswith(protocol.cmd_shield):
            # broadcast shield message
            send_str = protocol.server_shield_msg(client_id)
            for sock in sock_dict.values():
                send_message(sock, send_str)

        elif msg.startswith(protocol.cmd_talk):
            for sock in sock_dict.values():
                send_data(sock, data)

        elif msg.startswith(protocol.cmd_job):
            job_change_lock.acquire()  # lock job
            if not accepting:
                send_message(sock_dict[client_id], "房主已经宣布开始战斗，无法修改职业")
                # notify this player to restore its job
                send_message(sock_dict[client_id], protocol.server_job_msg(job_dict))
                job_change_lock.release()  # unlock job
                continue
            job_dict[client_id] = protocol.server_parse_job(msg)
            # broadcast current job state
            send_str = protocol.server_job_msg(job_dict)
            for sock in sock_dict.values():
                send_message(sock, send_str)
            job_change_lock.release()  # unlock job

        elif msg.startswith(protocol.cmd_join):
            name = protocol.server_parse_join(msg)
            # check if new comer's name has duplication
            is_dup = False
            for n in name_dict.values():
                if n == name:
                    is_dup = True
                    break
            if is_dup:
                send_message(sock_dict[client_id], protocol.server_reject_msg(3))
                continue
            # to here means join successfully
            name_dict[client_id] = name
            job_dict[client_id] = 0
            turn_dict[client_id] = 0
            # assign user 0 as leader
            if accepting and client_id == 0:
                send_message(sock_dict[client_id], protocol.server_leader_msg())
                msg = name + "进入房间，成为房主"
            else:
                msg = name + "进入房间"
            # broadcast join command including new player itself
            send_str = protocol.server_join_msg(name_dict)
            for sock in sock_dict.values():
                send_message(sock, send_str)
                send_message(sock, protocol.talk_msg(-1, msg))
            send_message(sock_dict[client_id], protocol.server_job_msg(job_dict))

        elif msg.startswith(protocol.cmd_exit):
            join_exit_lock.acquire()  # lock join/exit
            msg = name_dict[client_id] + "离开房间"
            send_message(sock_dict[client_id], protocol.server_exit_msg(client_id))
            for uid, sock in sock_dict.items():
                if uid == client_id:
                    continue
                send_message(sock, protocol.talk_msg(-1, msg))
                send_message(sock, protocol.server_exit_msg(client_id))
            sock_dict[client_id].close()
            del sock_dict[client_id]
            del job_dict[client_id]
            del name_dict[client_id]
            del turn_dict[client_id]
            join_exit_lock.release()  # unlock join/exit
            print(msg)
            return

        elif msg.startswith(protocol.cmd_battle):
            job_change_lock.acquire()  # lock job
            # check if at least one shield exist
            count = 0
            for job in job_dict.values():
                if job == 1:
                    count += 1
            if count < shield_min:
                send_message(sock_dict[client_id], protocol.server_battle_reject_msg())
                job_change_lock.release()
                continue
            accepting = False
            # broadcast battle command
            battle_str = protocol.server_battle_msg(name_dict, job_dict)
            turn_str = protocol.server_turn_msg(turn_dict)
            talk_str = protocol.talk_msg(-1, "通告全员，战斗开始，请遵守行动指示")
            for sock in sock_dict.values():
                send_message(sock, battle_str)
                send_message(sock, talk_str)
                send_message(sock, turn_str)
            job_change_lock.release()  # since not accept, job won't change even after release
            team_size = len(sock_dict)
            # send shield request
            while job_dict[shield_uid] != 1:
                shield_uid = (shield_uid + 1) % team_size
            send_message(sock_dict[shield_uid], protocol.server_shield_msg(-1))
            shield_uid = (shield_uid + 1) % team_size

        else:
            print("illegal message: %s" % msg)


# define global variables
serve_ip = "127.0.0.1"
serve_port = 5601
team_size = 6
shield_min = 5
shield_uid = 0
sock_dict = {}
name_dict = {}
join_exit_lock = threading.Lock()
job_dict = {}
job_change_lock = threading.Lock()
turn_dict = {}
turn_change_lock = threading.Lock()
accepting = True

# read config from file
for line in open("config.ini", 'r', encoding='utf-8'):
    if line.startswith('#'):  # this is comment line
        continue
    elif line.startswith("ip="):
        serve_ip = line[len("ip="):].strip()
    elif line.startswith("port="):
        serve_port = int(line[len("port="):].strip())
    elif line.startswith("team_size="):
        team_size = int(line[len("team_size="):].strip())
    elif line.startswith("shield_min="):
        shield_min = int(line[len("shield_min="):].strip())
    else:
        print("非法配置语句，请检查config.ini内容：%s" % line)
        exit(1)

# prepare server socket
sock_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock_server.settimeout(5)
sock_server.bind((serve_ip, serve_port))
sock_server.listen(1)
print("waiting for client connection on port %d..." % serve_port)

# accept connection from multiple clients
while accepting:
    try:
        sock_client, address = sock_server.accept()
    except socket.timeout as e:
        continue
    # to here means new one connected
    if not accepting:
        print("battle already started, reject connection from %s." % (address,))
        threading.Thread(target=thread_reject, args=[sock_client, 2]).start()
        break
    # now we need to check the dict, lock it to prevent exit event
    join_exit_lock.acquire()
    i = 0
    while sock_dict.__contains__(i) and i < team_size:
        i += 1
    if i == team_size:
        join_exit_lock.release()  # unlock
        print("team member full, reject connection from %s." % (address,))
        threading.Thread(target=thread_reject, args=[sock_client, 1]).start()
        continue
    # to here means new player accepted
    sock_dict[i] = sock_client
    join_exit_lock.release()  # unlock
    threading.Thread(target=thread_receive_data, args=[i]).start()
    print("%s connect in as user %d" % (address, i))

# to here means all users have exited
print("battle start, not accept more connections.")
sock_server.close()

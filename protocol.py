cmd_talk = "talk"
cmd_join = "join"
cmd_reject = "rej"
cmd_exit = "exit"
cmd_battle = "batl"
cmd_attack = "atk"
cmd_shield = "shd"
cmd_turn = "turn"
cmd_leader = "lead"
cmd_job = "job"

tag_user = "|usr|"
tag_data = "|dat|"

server_name = "AI"
job_list = ["自由", "防御", "治疗", "输出"]


# reject reason code: 1=room full, 2=battle already start, 3=name duplicate


def extract_pack(buf):  # return exactly one complete pack message
    end_idx = buf.find('\n'.encode('UTF-8'))
    if end_idx < 0:
        return b'', buf
    elif end_idx + 1 == len(buf):
        return buf, b''
    else:
        return buf[:end_idx + 1], buf[end_idx + 1:]


# talk |usr|1 |dat|hello \n
def talk_msg(uid, message):
    return ''.join([cmd_talk, tag_user, str(uid), tag_data, message, '\n'])


# talk |usr|1 |dat|hello \n
def client_parse_talk(msg, name_dict):  # return talk string including '\n' tail
    id_start = msg.find(tag_user, len(cmd_talk)) + len(tag_user)
    id_end = msg.find(tag_data)
    uid = int(msg[id_start:id_end])
    if uid < 0:
        name = server_name
    else:
        name = name_dict[uid]
    id_start = id_end + len(tag_data)
    return ''.join([name, ': ', msg[id_start:]])


# send join message: join |usr|alice \n
def client_join_msg(name):
    return ''.join([cmd_join, tag_user, name, '\n'])


# join |usr|alice
def server_parse_join(msg):
    return msg[len(cmd_join) + len(tag_user):len(msg) - 1]


# join |usr|alice |dat|1 |usr|kitty |dat|2 \n
def server_join_msg(name_dict):
    buf = [cmd_join]
    for uid, name in name_dict.items():
        buf.extend([tag_user, name, tag_data, str(uid)])
    buf.append('\n')
    return ''.join(buf)


# join |usr|alice |dat|1 |usr|kitty |dat|2 \n
def client_parse_join(msg):  # return uid array and name array
    names = []
    uids = []
    id_end = msg.find(tag_user, len(cmd_join))
    while True:
        id_start = id_end + len(tag_user)
        id_end = msg.find(tag_data, id_start)
        names.append(msg[id_start:id_end])
        id_start = id_end + len(tag_data)
        id_end = msg.find(tag_user, id_start)
        uids.append(int(msg[id_start:id_end]))
        if msg[id_end] == '\n':
            break
    return uids, names


# lead \n
def server_leader_msg():
    return cmd_leader + '\n'


# batl \n
def client_battle_msg():
    return cmd_battle + '\n'


# only batl\n when no shield
def server_battle_reject_msg():
    return cmd_battle + '\n'


def client_battle_reject_check(msg):
    return msg[len(cmd_battle)] == '\n'


# batl |usr|alice |dat|1 |dat|2  |usr|kitty |dat|2 |dat|2 \n
def server_battle_msg(name_dict, job_dict):
    buf = [cmd_battle]
    for uid, name in name_dict.items():
        buf.extend([tag_user, name])
        buf.extend([tag_data, str(uid)])
        buf.extend([tag_data, str(job_dict[uid])])
    buf.append('\n')
    return ''.join(buf)


# batl |usr|alice |dat|1 |dat|2  |usr|kitty |dat|2 |dat|2 \n
def client_parse_battle(msg):  # return uid array, name array, job array
    uids = []
    names = []
    jobs = []
    id_end = msg.find(tag_user, len(cmd_battle))
    while True:
        id_start = id_end + len(tag_user)
        id_end = msg.find(tag_data, id_start)
        names.append(msg[id_start:id_end])
        id_start = id_end + len(tag_data)
        id_end = msg.find(tag_data, id_start)
        uids.append(int(msg[id_start:id_end]))
        id_start = id_end + len(tag_data)
        id_end = msg.find(tag_user, id_start)
        jobs.append(int(msg[id_start:id_end]))
        if msg[id_end] == '\n':
            break
    return uids, names, jobs


# rej 1 \n
def server_reject_msg(err_id):
    return ''.join([cmd_reject, str(err_id), '\n'])


def client_parse_reject(msg):  # return reason id
    return int(msg[len(cmd_reject):len(msg) - 1])


# exit \n
def client_exit_msg():
    return cmd_exit + '\n'


# exit 2 \n
def server_exit_msg(uid):
    return ''.join([cmd_exit, str(uid), '\n'])


# exit 2 \n
def client_parse_exit(msg):  # return uid
    return int(msg[len(cmd_exit):len(msg) - 1])


# job 2 \n
def client_job_msg(job_name):
    i = 0
    while i < len(job_list):
        if job_list[i] == job_name:
            return ''.join([cmd_job, str(i), '\n'])
        i += 1
    return ''.join([cmd_job, str(0), '\n'])


def server_parse_job(msg):  # return job id
    return int(msg[len(cmd_job):len(msg) - 1])


# job |usr|1 |dat|1 |usr|2 |dat|1 \n
def server_job_msg(job_dict):
    buf = [cmd_job]
    for uid, job_id in job_dict.items():
        buf.extend([tag_user, str(uid), tag_data, str(job_id)])
    buf.append('\n')
    return ''.join(buf)


def client_parse_job(msg):  # return uid and job id array
    uids = []
    job_ids = []
    id_end = msg.find(tag_user, len(cmd_job))
    while True:
        id_start = id_end + len(tag_user)
        id_end = msg.find(tag_data, id_start)
        uids.append(int(msg[id_start:id_end]))
        id_start = id_end + len(tag_data)
        id_end = msg.find(tag_user, id_start)
        job_ids.append(int(msg[id_start:id_end]))
        if msg[id_end] == '\n':
            break
    return uids, job_ids


# turn |usr|1 |dat|6 |usr|2 |dat|6 \n
def server_turn_msg(turn_dict):
    buf = [cmd_turn]
    for uid, turn in turn_dict.items():
        buf.extend([tag_user, str(uid), tag_data, str(turn)])
    buf.append('\n')
    return ''.join(buf)


# turn |usr|1 |dat|6 |usr|2 |dat|6 \n
def client_parse_turn(msg):  # return uid array and turn number array
    uids = []
    turns = []
    id_end = msg.find(tag_user, len(cmd_turn))
    while True:
        id_start = id_end + len(tag_user)
        id_end = msg.find(tag_data, id_start)
        uids.append(int(msg[id_start:id_end]))
        id_start = id_end + len(tag_data)
        id_end = msg.find(tag_user, id_start)
        turns.append(int(msg[id_start:id_end]))
        if msg[id_end] == '\n':
            break
    return uids, turns


# atk \n
def client_attack_msg():
    return cmd_attack + '\n'


# shd \n
def client_shield_msg():
    return cmd_shield + '\n'


# shd 3 \n
# when uid=-1, it's instruction to require receiver to use shield, otherwise it's
# a reply to clients shield message.
def server_shield_msg(uid):
    return ''.join([cmd_shield, str(uid), '\n'])


# shd 3 \n
def client_parse_shield(msg):  # return uid
    return int(msg[len(cmd_shield):len(msg) - 1])

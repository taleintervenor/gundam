#!/usr/bin/python
# -*- coding: UTF-8 -*-
# 文件名：client.py

import socket
import threading
import tkinter as tk

import protocol


def send_message(msg):
    try:
        sock.send(msg.encode('utf-8'))
    except socket.error as e:
        txt_talk.insert("end", "%s: 发送失败，错误：%s\n" % (protocol.server_name, e))


def new_instruct(msg):
    lab_instr_var.set(msg)
    lab_instruct.config(background="yellow")
    lab_instruct.after(1000, lambda: lab_instruct.config(background="SystemButtonFace"))


def thread_receive_data():
    global self_uid, get_shield, is_connected
    lock_recv.acquire()
    buf = b''
    while True:
        # receive until message is complete
        while True:
            data, buf = protocol.extract_pack(buf)
            if len(data) > 0:
                break
            else:
                buf = buf + sock.recv(128)
        msg = data.decode('utf-8')
        # handle the message
        if msg.startswith(protocol.cmd_turn):
            self_turn = 0
            uids, turns = protocol.client_parse_turn(msg)
            # update turn count for each player
            i = 0
            while i < len(uids):
                label_turn_vars[uids[i]].set(turns[i])
                if uids[i] == self_uid:
                    self_turn = turns[i]
                i += 1
            # update action button state
            wait_other = False
            i = 0
            while i < len(uids):
                if turns[i] < self_turn:
                    wait_other = True
                    break
                i += 1
            if wait_other:
                btn_attack.config(state="disabled")
                new_instruct("等待队友完成本回合行动……（除攻击推进回合、使用英灵盾以外的行动均可在等待期间进行）")
            elif not get_shield:
                btn_attack.config(state="disabled")
                new_instruct("等待队友使用英灵盾……（除攻击推进回合、使用英灵盾以外的行动均可在等待期间进行）")

        elif msg.startswith(protocol.cmd_shield):
            uid = protocol.client_parse_shield(msg)
            if uid < 0:
                new_instruct("轮到你使用英灵盾")
                btn_shield.config(state="normal")
                continue
            if uid == self_uid:
                btn_shield.config(state="disabled")
                new_instruct("已使用英灵盾，请尽快攻击推进回合")
            else:
                new_instruct("%s已使用英灵盾，请尽快攻击推进回合" % player_name_dict[uid])
            btn_attack.config(state="normal")
            get_shield = True

        elif msg.startswith(protocol.cmd_talk):
            # add new talk message to talk window
            txt_talk.insert("end", protocol.client_parse_talk(msg, player_name_dict))

        elif msg.startswith(protocol.cmd_job):
            # update job state
            uids, job_ids = protocol.client_parse_job(msg)
            i = 0
            while i < len(uids):
                label_job_vars[uids[i]].set(protocol.job_list[job_ids[i]])
                i += 1

        elif msg.startswith(protocol.cmd_join):
            if self_uid < 0:  # this is the first join message, ACK to yourself's join request
                new_instruct("等待房主宣布开始战斗，请在此期间选定自己的职业")
                opm_job_var.set(protocol.job_list[0])
            uids, names = protocol.client_parse_join(msg)
            i = 0
            while i < len(uids):
                if names[i] == ety_user.get():
                    self_uid = uids[i]
                player_name_dict[uids[i]] = names[i]
                # update name display according to new join message
                label_name_vars[uids[i]].set(names[i])
                i += 1
            # enable job/talk function
            opm_job.config(state="normal")
            btn_talk.config(state="normal")

        elif msg.startswith(protocol.cmd_reject):
            err_id = protocol.client_parse_reject(msg)
            if err_id < 3:  # room full or battle started
                is_connected = False
                sock.close()
                lock_recv.release()
                ety_user.config(state="normal")
                ety_ip.config(state="normal")
                ety_port.config(state="normal")
                btn_connect.config(state="normal")
                if err_id == 1:
                    new_instruct("房间目前满员，请稍后重试或寻找其他房间")
                else:
                    new_instruct("战斗已经开始，请寻找其他房间")
                return
            else:  # err_id == 3, name duplicate
                ety_user.config(state="normal")
                btn_connect.config(state="normal")
                new_instruct("你的昵称与房间内其他玩家重复，请修改后重新进入")

        elif msg.startswith(protocol.cmd_leader):
            btn_battle.config(state="normal")

        elif msg.startswith(protocol.cmd_battle):
            if protocol.client_battle_reject_check(msg):
                new_instruct("不能在盾役不够的情况下开始战斗，请与队员协调职业分工")
                continue
            uids, names, jobs = protocol.client_parse_battle(msg)
            i = 0
            while i < len(uids):
                player_name_dict[uids[i]] = names[i]
                # update name/job display according to battle message
                label_name_vars[uids[i]].set(names[i])
                label_job_vars[uids[i]].set(protocol.job_list[jobs[i]])
                i += 1
            # disable battle and job button
            btn_battle.config(state="disabled")
            opm_job.config(state="disabled")

        elif msg.startswith(protocol.cmd_exit):
            uid = protocol.client_parse_exit(msg)
            if uid == self_uid:  # ACK for your exit notify
                sock.close()
                lock_recv.release()
                return
            else:  # other's exit notify
                del player_name_dict[uid]
                label_name_vars[uid].set("")
                label_job_vars[uid].set(protocol.job_list[0])
                label_turn_vars[uid].set(0)

        else:
            txt_talk.insert("end", "AI: 非法信息：%s\n" % msg)


def win_cb_close():
    send_message(protocol.client_exit_msg())
    lock_recv.acquire()  # wait receive thread exit
    lock_recv.release()
    main_win.destroy()


def ety_common_cb_focus(event):
    ety = event.widget
    if ety.get() == ety_default_txt_dict[ety]:
        ety.delete(0, "end")


def ety_common_cb_unfocus(event):
    ety = event.widget
    if len(ety.get()) == 0:
        ety.insert(0, ety_default_txt_dict[ety])


def btn_connect_cb_click():
    global sock, is_connected
    user = ety_user.get()
    if len(user) == 0:
        new_instruct("请先设置你的昵称，进入房间后无法修改！")
        return
    if user == protocol.server_name:
        new_instruct("你不能使用服务器保留昵称，请更换其他昵称。")
        return
    if not is_connected:
        sock = socket.socket()
        addr = ety_ip.get()
        port = int(ety_port.get())
        sock.settimeout(10)
        try:
            sock.connect((addr, port))
        except Exception as e:
            txt_talk.insert("end", "AI: 连接%s:%d失败，错误：('127.0.0.1', %s\n" % (addr, port, e))
            return
        finally:
            sock.settimeout(None)
        # to here means wo connected successfully
        threading.Thread(target=thread_receive_data).start()
        is_connected = True
        ety_ip.config(state="disabled")
        ety_port.config(state="disabled")
    ety_user.config(state="disabled")
    btn_connect.config(state="disabled")
    # to here we make sure to have been connected
    send_message(protocol.client_join_msg(user))


def opm_job_cb_change(*args):
    send_message(protocol.client_job_msg(opm_job_var.get()))


def btn_battle_cb_click():
    send_message(protocol.client_battle_msg())
    txt_talk.insert("end", "%s: 申请开始战斗（如长时间未收到全体通告，尝试再次宣布）\n" % player_name_dict[self_uid])


def btn_attack_cb_click():
    send_message(protocol.client_attack_msg())
    global get_shield
    get_shield = False


def btn_shield_cb_click():
    send_message(protocol.client_shield_msg())


def btn_talk_cb_click():
    buf = ety_talk.get()
    if len(buf) == 0:
        return
    send_message(protocol.talk_msg(self_uid, buf))
    ety_talk.delete(0, tk.END)


# define global variable
is_connected = False
ety_ip_default = "127.0.0.1"
ety_port_default = "5601"
ety_user_default = "匿名"
team_size = 2
self_uid = -1
get_shield = False
player_name_dict = {}
label_name_vars = []
label_job_vars = []
label_turn_vars = []
ety_default_txt_dict = {}
lock_recv = threading.Lock()
sock = socket.socket()

# set GUI
main_win = tk.Tk()
main_win.title("Kamihime高达驾驶系统")

# set server ip:port entry
tk.Label(main_win, text="房间地址").grid(row=0, sticky="W")
ety_ip = tk.Entry(main_win, borderwidth=3, relief='ridge', width=20)
ety_ip.insert(0, ety_ip_default)
ety_default_txt_dict[ety_ip] = ety_ip_default
ety_ip.bind("<FocusIn>", ety_common_cb_focus)
ety_ip.bind("<FocusOut>", ety_common_cb_unfocus)
ety_ip.grid(row=0, column=1, columnspan=4, sticky="W")
tk.Label(main_win, text=" : ").grid(row=0, column=5)
ety_port = tk.Entry(main_win, borderwidth=3, relief='ridge', width=5)
ety_port.insert(0, ety_port_default)
ety_default_txt_dict[ety_port] = ety_port_default
ety_port.bind("<FocusIn>", ety_common_cb_focus)
ety_port.bind("<FocusOut>", ety_common_cb_unfocus)
ety_port.grid(row=0, column=6, sticky="W")
# set user name entry
tk.Label(main_win, text="你的昵称").grid(row=1, sticky="W")
ety_user = tk.Entry(main_win, borderwidth=3, relief='ridge', width=20)
ety_user.insert(0, ety_user_default)
ety_default_txt_dict[ety_user] = ety_user_default
ety_user.bind("<FocusIn>", ety_common_cb_focus)
ety_user.bind("<FocusOut>", ety_common_cb_unfocus)
ety_user.grid(row=1, column=1, columnspan=8, sticky="W")
# set server connection button
btn_connect = tk.Button(main_win, text='进入房间', command=btn_connect_cb_click)
btn_connect.grid(row=1, column=9, sticky="E")

# set job option menu
tk.Label(main_win, text="职业分工").grid(row=2, sticky="W")
opm_job_var = tk.StringVar()
opm_job_var.set(protocol.job_list[0])
opm_job = tk.OptionMenu(main_win, opm_job_var, *protocol.job_list)
opm_job.config(state="disabled")
opm_job.grid(row=2, column=1, columnspan=3, sticky='W')
opm_job_var.trace('w', opm_job_cb_change)
# set battle start button
btn_battle = tk.Button(main_win, text='开始战斗', state="disabled", command=btn_battle_cb_click)
btn_battle.grid(row=2, column=9, sticky="E")

# set member info labels
grp_member = tk.LabelFrame(main_win, text="队员信息")
grp_member.grid(row=3, rowspan=5, columnspan=10, sticky="W")
i = 0
for y in range(2):
    tk.Label(grp_member, text="昵称").grid(row=y * 2 + 4, column=0)
    tk.Label(grp_member, text="职业/回合").grid(row=y * 2 + 5, column=0)
    for x in range(3):
        label_name_vars.append(tk.StringVar())
        label_name_vars[i].set("")
        tk.Label(grp_member, width=13, borderwidth=2, relief='ridge', textvariable=label_name_vars[i]) \
            .grid(row=y * 2 + 4, column=x * 3 + 1, columnspan=3)
        label_job_vars.append(tk.StringVar())
        label_job_vars[i].set(protocol.job_list[0])
        tk.Label(grp_member, width=6, borderwidth=2, relief='ridge', textvariable=label_job_vars[i]) \
            .grid(row=y * 2 + 5, column=x * 3 + 1, columnspan=2, sticky="W")
        label_turn_vars.append(tk.IntVar())
        label_turn_vars[i].set(0)
        tk.Label(grp_member, width=4, borderwidth=2, relief='ridge', textvariable=label_turn_vars[i]) \
            .grid(row=y * 2 + 5, column=x * 3 + 3, sticky="E")
        i += 1

# set instruction msg box
grp_action = tk.LabelFrame(main_win, text="行动指示")
grp_action.grid(row=8, column=0, rowspan=4, columnspan=10)
lab_instr_var = tk.StringVar()
lab_instruct = tk.Label(grp_action, height=2, width=50, anchor='nw', justify='left', borderwidth=2, relief='ridge',
                        textvariable=lab_instr_var)
lab_instruct.grid(row=9, rowspan=2, columnspan=10)
lab_instruct.update()
lab_instruct.config(wraplength=lab_instruct.winfo_width() - 10)
lab_instruct.after_idle(new_instruct, "请先设置你的昵称，进入房间后无法修改！")
# set action buttons
btn_attack = tk.Button(grp_action, text='攻击', width=10, state="disabled", command=btn_attack_cb_click)
btn_attack.grid(row=11, columnspan=5)
btn_shield = tk.Button(grp_action, text='英灵盾', width=10, state="disabled", command=btn_shield_cb_click)
btn_shield.grid(row=11, column=5, columnspan=5)

# set talk message window
txt_talk = tk.Text(main_win, borderwidth=2, relief='ridge', width=50, height=20)
txt_talk.grid(row=12, columnspan=10)
# set talk input box
ety_talk = tk.Entry(main_win, borderwidth=3, relief='ridge', width=40)
ety_talk.grid(row=13, columnspan=9)
# set talk button
btn_talk = tk.Button(main_win, text='发消息', state="disabled", command=btn_talk_cb_click)
btn_talk.grid(row=13, column=9, sticky="E")

# 进入消息循环
main_win.protocol("WM_DELETE_WINDOW", win_cb_close)
main_win.mainloop()

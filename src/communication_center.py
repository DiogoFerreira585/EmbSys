import utilities.network   as network
from utilities.message import encode_packet,decode_packet
from utilities.log     import log_cnsl
from time              import sleep
import socket
import threading

'''
    ATTENTION:
        I AM AWARE THERE ARE SOME COMMUNICATION BUGS
        WHEN CONNECTION FAILS WITH SOMEONE ALL THE CONNECTIONS SHOULD BE DROPPED AND TRIED AGAIN
        IF YOU UNCOVER BUGS
        === HIT ME ON DMs ===
    TelmoRibeiro
'''

# EVENTS:
MULTIM_EVENT = threading.Event() # used to notify the multimedia socket is known
MOBILE_EVENT = threading.Event() # used to notify the mobile     socket is known
SENSOR_EVENT = threading.Event() # used to notify the sensor processing function

def stop(service,client_socket):
    match service:
        case MOBILE_SERVICE if MOBILE_SERVICE == network.MOBILE_SERVER:
            global MOBILE_SOCKET
            MOBILE_SOCKET = client_socket
            MOBILE_EVENT.set()
            while not MULTIM_EVENT.is_set():
                continue
        case MULTIM_SERVICE if MULTIM_SERVICE == network.MULTIM_SERVER:
            global MULTIM_SOCKET
            MULTIM_SOCKET = client_socket
            MULTIM_EVENT.set()
            while not MOBILE_EVENT.is_set():
                continue
        case _:
            log_cnsl(service,f"service={service} not supported!")
            client_socket.close()
            raise RuntimeError(f"service={service} not supported!")

def play(service,client_socket):
    try:
        _,data_encd = encode_packet(0,"SYNC")
        log_cnsl(service,"sending SYNC...")
        client_socket.sendall(data_encd)
        ##########
        _,_,msg_content = decode_packet(client_socket.recv(1024))
        log_cnsl(service,"received SYNC_ACK!")
        if msg_content != "SYNC_ACK":
            log_cnsl(service,f"SYNC_ACK expected yet {msg_content} received")
            client_socket.close()
    except Exception as e:
        log_cnsl(service,f"caught: {e}")
        client_socket.close()
        raise RuntimeError(f"caught: {e}")

def server(service):
    server_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM) # tcp connection
    SERVICE_IPV4  = network.SERVER_IPV4 
    SERVICE_PORT  = network.service_port(service)
    server_socket.bind((SERVICE_IPV4,SERVICE_PORT))
    server_socket.listen()
    log_cnsl(service,"listening...")
    try:
        while True:
            client_socket,client_address = server_socket.accept()
            log_cnsl(service,f"connection established with {client_address}!")
            stop(service,client_socket)
            play(service,client_socket)
            try:
                while True:
                    data_recv = client_socket.recv(1024)
                    if not data_recv:
                        break
                    msg_ID,msg_timestamp,msg_content = decode_packet(data_recv)
                    log_cnsl(service,f"received {msg_content}!")
                    message_control_thread = threading.Thread(target=message_control,args=(service,msg_ID,msg_timestamp,msg_content,))
                    message_control_thread.start()
            except Exception as e:
                log_cnsl(service,f"caught: {e}")
                client_socket.close()
                raise RuntimeError(f"caught: {e}")
    except KeyboardInterrupt:
        log_cnsl(service,"shutting down...")
    finally:
        server_socket.close()

def message_control(service,msg_ID,msg_timestamp,msg_content):
    # @ telmo - not testing for msg_src...
    match msg_content:
        case FLAG if FLAG in ["OPEN_R","CLOSE_R","PHOTO_R"]:
            client_socket = MULTIM_SOCKET
            if SENSOR_EVENT.is_set() and FLAG != "PHOTO_R":
                SENSOR_EVENT.clear()
            _,data_encd = encode_packet(msg_ID,msg_content,msg_timestamp)
            try:              
                log_cnsl(service,f"sending {msg_content}...")
                client_socket.sendall(data_encd)
            except Exception as e:
                log_cnsl(service,f"caught: {e}")
                client_socket.close()
                raise RuntimeError(f"caught: {e}")
        case FLAG if FLAG in ["OPEN_E","CLOSE_E","PHOTO_E"]:
            client_socket = MOBILE_SOCKET
            _,data_encd = encode_packet(msg_ID,msg_content,msg_timestamp)
            try:
                log_cnsl(service,f"sending {msg_content}...")
                client_socket.sendall(data_encd)
            except Exception as e:
                log_cnsl(service,f"caught: {e}")
                client_socket.close()
                raise RuntimeError(f"caught: {e}")
        case FLAG if FLAG in ["SENSOR_E"]:
            client_socket = MOBILE_SOCKET
            _,data_encd = encode_packet(msg_ID,msg_content,msg_timestamp)
            try:
                log_cnsl(service,f"sending {msg_content}...")
                client_socket.sendall(data_encd)
                SENSOR_EVENT.set()
                sleep(5)
                # @ telmo - what shall happen if SENSOR_E arrives while SENSOR_E is processed?
                if SENSOR_EVENT.is_set():
                    client_socket = MULTIM_SOCKET
                    _,data_encd = encode_packet(msg_ID,"CLOSE_R")
                    log_cnsl(service,f"sending CLOSE_R...")
                    client_socket.sendall(data_encd)
                SENSOR_EVENT.clear()
            except Exception as e:
                log_cnsl(service,f"caught: {e}")
                client_socket.close()
                raise RuntimeError(f"caught: {e}")
        case _: 
            log_cnsl(service,f"service={msg_content} not supported!")
            raise RuntimeError(f"service={msg_content} not supported!")

def main():
    mobile_thread = threading.Thread(target=server,args=(network.MOBILE_SERVER,))
    multim_thread = threading.Thread(target=server,args=(network.MULTIM_SERVER,))
    mobile_thread.start()
    multim_thread.start()
    # RUNNING THREADS #

if __name__ == "__main__": main()
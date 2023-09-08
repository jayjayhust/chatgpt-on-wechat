# REF URL: https://blog.csdn.net/qq_42069296/article/details/132432835

# 方法1
import uuid
 
# 获取本机MAC地址
# def get_local_mac():
#     mac_address = ':'.join(hex(uuid.getnode())[2:].zfill(12)[i:i + 2] for i in range(0, 12, 2))
#     print("MAC address:", mac_address)  # 输出形如：MAC address: a8:93:4a:4d:59:45
 
# if __name__=='__main__':
#     get_local_mac()

# 方法2
from psutil import net_if_addrs


# 获取所有MAC地址
def list_all_mac():
    for k, v in net_if_addrs().items():
        print('*' * 100)
        print(k)  # 输出形如：以太网/vEthernet (Default Switch)/本地连接* 1/VMware Network Adapter VMnet1/WLAN/Loopback Pseudo-Interface 1
        for item in v:
            address = item[1]
            if '-' in address and len(address)==17:
                print(address)  # 输出形如：B0-25-AA-4C-55-AC
            if '.' in address:
                print(address)  # 输出形如：192.168.0.28


# 获取无线网卡MAC地址
def list_lan_mac():
    for k, v in net_if_addrs().items():
        print('*' * 100)
        print(k)  # 输出形如：以太网/vEthernet (Default Switch)/本地连接* 1/VMware Network Adapter VMnet1/WLAN/Loopback Pseudo-Interface 1
        if k in ["WLAN"]:  # 类型为无线网卡
            for item in v:
                address = item[1]
                if '-' in address and len(address)==17:
                    print(address)  # 输出形如：B0-25-AA-4C-55-AC

class mac_derive(object):
    def __init__(self):
        pass
    
    # 获取所有MAC地址
    def get_all_mac(self):
        for k, v in net_if_addrs().items():
            print('*' * 100)
            print(k)  # 输出形如：以太网/vEthernet (Default Switch)/本地连接* 1/VMware Network Adapter VMnet1/WLAN/Loopback Pseudo-Interface 1
            for item in v:
                address = item[1]
                if '-' in address and len(address)==17:
                    print(address)  # 输出形如：B0-25-AA-4C-55-AC
                if '.' in address:
                    print(address)  # 输出形如：192.168.0.28

    # 获取无线网卡MAC地址
    def get_lan_mac(self):
        for k, v in net_if_addrs().items():
            print('*' * 100)
            print(k)  # 输出形如：以太网/vEthernet (Default Switch)/本地连接* 1/VMware Network Adapter VMnet1/WLAN/Loopback Pseudo-Interface 1
            if k in ["WLAN"]:  # 类型为无线网卡
                for item in v:
                    address = item[1]
                    if '-' in address and len(address)==17:
                        print(address)  # 输出形如：B0-25-AA-4C-55-AC
                        return address


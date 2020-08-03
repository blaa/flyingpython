import network
import socket
import struct
import machine
import time

def start_ap():
    ssid = "Flyer"
    password = "groundisthelimit"
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid=ssid, password=password)
    print(ap.ifconfig())

class Flyer:
    def __init__(self):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.s.bind(('', 4242))
        except OSError:
            print("Binding port error - ignoring")

        # self.s.setblocking(False)
        self.pwm_a = machine.PWM(machine.Pin(5))
        self.pwm_b = machine.PWM(machine.Pin(4))
        self.pwm_c = machine.PWM(machine.Pin(0))
        self.pwm_d = machine.PWM(machine.Pin(14))
        self.pwms = [self.pwm_a, self.pwm_b, self.pwm_c, self.pwm_d]
        for pwm in self.pwms:
            print("Initializing", pwm)
            pwm.freq(100)
            # duty 50 - band
            # 140 - half
            # 230 - max

        self.security_ticks = 0
        self.sec_timer = machine.Timer(-1)
        self.sec_timer.init(period=200,
                            mode=machine.Timer.PERIODIC,
                            callback=self.tick)

    def tick(self, timer):
        "Security timer"
        self.security_ticks += 1
        if self.security_ticks > 6:
            print("Lost connection! Disabling engine!")
            self.pwm_d.duty(0)

    def __del__(self):
        self.s.close()
        del self.s

    def fly(self):
        SLEEP_TIME = 1 / 100
        cnt = 0
        while True:
            time.sleep(SLEEP_TIME)

            # This will block
            data = self.s.recv(50)
            try:
                unpacked = struct.unpack("HHHHBB", data)
                pwm_a, pwm_b, pwm_c, pwm_d, toggle_a, toggle_b = unpacked
            except Exception:
                print("Ignoring unpack error")
                time.sleep(0.01)
                continue
            data = [pwm_a, pwm_b, pwm_c, pwm_d]
            for pwm, duty in zip(self.pwms, data):
                pwm.duty(duty)
            cnt += 1
            if cnt % 20 == 0:
                print(cnt, "cur: ", data)
            self.security_ticks = 0


def main():
    start_ap()
    flyer = Flyer()
    try:
        flyer.fly()
    except KeyboardInterrupt:
        print("Interrupted")
        del flyer
    finally:
        del flyer

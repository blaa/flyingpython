#!/usr/bin/env python3

import time
import pygame
import struct
import socket

JOY_ID = 0
PITCH_AXIS = 1
ROLL_AXIS = 0
ENGINE_AXIS = 4

SCALE_PITCH_FACTOR = 0.3
ROLL_SCALE_FACTOR = 0.4
UPDATES_PER_S = 20
ENGINE_DELAY = UPDATES_PER_S * 2

class Flyer:
    "Flyer interface"

    def __init__(self, address):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.address = address

    def xmit(self, data):
        self.s.sendto(data, self.address)
        pass

    def control(self, pwm_a, pwm_b, pwm_c, pwm_d, toggle_a, toggle_b):
        data = struct.pack("HHHHBB", pwm_a, pwm_b,
                           pwm_c, pwm_d, toggle_a, toggle_b)
        self.xmit(data)


class Control:
    "Control flyer using a pad/joystick"

    def __init__(self, flyer, joy_id):
        self.flyer = flyer
        self.joystick = self._init_pygame(joy_id)

        self.trim_pitch = 0.2
        self.trim_roll = 0
        self.engine_power = 0
        self.engine_toggle_check = 0
        self.engine_delay = 0

    def _init_pygame(self, joy_id=0):
        "Pygame initialization + debug"
        print("- Initialize pygame")
        pygame.init()
        print("- Initialize joystick")
        pygame.joystick.init()

        joysticks = pygame.joystick.get_count()
        print(f"- Detected {joysticks} joysticks")
        joystick = pygame.joystick.Joystick(joy_id)
        print(f"- Opening joystick: {joystick.get_name()}")
        joystick.init()
        axes = joystick.get_numaxes()
        hats = joystick.get_numhats()
        buts = joystick.get_numbuttons()
        print("  AXES: %d HATS: %d BUTS: %d" % (axes, hats, buts))

        pygame.time.set_timer(pygame.USEREVENT, 1000 // UPDATES_PER_S)
        return joystick

    def loop(self):
        while True:
            event = pygame.event.wait()
            if event.type == pygame.JOYAXISMOTION:
                # Meh.
                pass
            elif event.type == pygame.USEREVENT:
                self.do_move()
            elif event.type == pygame.JOYBUTTONDOWN:
                self.do_buttons(event.button)
            elif event.type == pygame.JOYBUTTONUP:
                pass
            else:
                print("Different joystick event", event.type)

    def to_servo(self, value, middle, val_range, low, high):
        output = middle + value * val_range
        output = max(low, output)
        output = min(high, output)
        return int(output)

    def do_move(self):
        "Movement, updated periodically"
        pitch = self.joystick.get_axis(PITCH_AXIS) * SCALE_PITCH_FACTOR
        roll = self.joystick.get_axis(ROLL_AXIS)
        throttle = -self.joystick.get_axis(ENGINE_AXIS)

        pitch_trimmed = pitch - self.trim_pitch
        roll_trimmed = roll - self.trim_roll

        MAX = 254
        MIDDLE_A = 132
        MIDDLE_B = 177
        MIDDLE_C = 190

        # Equalize angle on both sides
        if pitch_trimmed < 0.0:
            # Trim right wing
            PITCH_BALANCE_A = 0.5
        else:
            PITCH_BALANCE_A = 1.0
        PITCH_BALANCE_B = 1.0

        engine_power = self.calculate_engine_power(throttle)

        pwm_a = self.to_servo(PITCH_BALANCE_A * pitch_trimmed
                              - ROLL_SCALE_FACTOR * roll_trimmed,
                              MIDDLE_A, MAX/2, 90, 176)
        pwm_b = self.to_servo(PITCH_BALANCE_B * pitch_trimmed
                              + ROLL_SCALE_FACTOR * roll_trimmed,
                              MIDDLE_B, MAX/2, 92, 221)
        pwm_c = self.to_servo(-pitch_trimmed, MIDDLE_C, MAX/2, 110, 254)

        print(f"P{pitch:5.2f} R{roll:5.2f} E {throttle:5.2f} T:{self.trim_pitch:5.2f} {self.trim_roll:5.2f}"
              f" -> {pwm_a:3d} {pwm_b:3d} {pwm_c:3d} {engine_power:4d}")
        self.flyer.control(pwm_a, pwm_b, pwm_c, engine_power, 0, 0)

    def calculate_engine_power(self, throttle):
        "Update engine power using current throttle setting."
        if self.engine_delay:
            self.engine_delay -= 1
            return 0

        if self.engine_toggle_check == 0 and throttle > 0.9:
            self.engine_toggle_check = 1
            print("ENGINE: High range check OK")
        elif self.engine_toggle_check == 1 and throttle < -0.9:
            self.engine_toggle_check = 2
            print("ENGINE: Low range check OK - engine enabled")
            # Ready, range OK
        elif self.engine_toggle_check == 2:
            # Calculate engine power change
            if throttle < -0.98:
                # Immediate/emergency off
                self.engine_delay = ENGINE_DELAY
                self.engine_power = 0
            elif throttle > 0.1:
                throttle -= 0.1
                # In 1.5 seconds to max
                SECONDS = 1.0
                DELTA = 1 + 1023 / UPDATES_PER_S / SECONDS
                self.engine_power += int(DELTA * throttle)
            elif throttle < 0.0:
                # In 0.5 seconds to min
                SECONDS = 0.5
                DELTA = 1 + 1023 / UPDATES_PER_S / SECONDS
                self.engine_power += int(DELTA * throttle)
        self.engine_power = max(0, min(self.engine_power, 1023))
        return self.engine_power

    def trim(self):
        pitch = self.joystick.get_axis(PITCH_AXIS) * SCALE_PITCH_FACTOR
        roll = self.joystick.get_axis(ROLL_AXIS)

        pitch_trimmed = pitch - self.trim_pitch
        roll_trimmed = roll - self.trim_roll

        self.trim_pitch -= pitch
        self.trim_roll -= roll
        print(f"Trimmed to pitch {pitch} and roll {roll}")

    def do_buttons(self, button):
        BUTTON_A = 0
        BUTTON_B = 1
        if button == BUTTON_A:
            self.trim()
        if button == BUTTON_B:
            self.trim_pitch = 0
            self.trim_roll = 0
            print("Reset trim")
        else:
            print("Unhandled button", button)

def main():
    address = ("192.168.4.1", 4242)
    flyer = Flyer(address)
    flyer.control(140, 140, 140, 0, 0, 0)

    control = Control(flyer, JOY_ID)
    try:
        control.loop()
    except KeyboardInterrupt:
        print("Interrupted")
        return

if __name__ == "__main__":
    main()

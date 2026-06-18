import opcode
import time
import tkinter as tk
from tkinter.filedialog import askopenfilename
import threading
import sys
import random
import pygame

class Chip8:
    """Represents the state of a CHIP-8 virtual machine, including memory, registers,
    graphics, timers, and input. Provides methods to load ROMs and execute cycles."""
    def __init__(self):
        self.memory = [0] * 4096
        self.v = [0] * 16
        self.i = 0
        self.pc = 0x200  # programs start at 0x200
        self.gfx = [[0] * 64 for _ in range(32)]
        self.delay_timer = 0
        self.sound_timer = 0
        self.stack = []
        self.key = [0] * 16
        self.font_set = [
            0xF0, 0x90, 0x90, 0x90, 0xF0, # 0
            0x20, 0x60, 0x20, 0x20, 0x70, # 1
            0xF0, 0x10, 0xF0, 0x80, 0xF0, # 2
            0xF0, 0x10, 0xF0, 0x10, 0xF0, # 3
            0x90, 0x90, 0xF0, 0x10, 0x10, # 4
            0xF0, 0x80, 0xF0, 0x10, 0xF0, # 5
            0xF0, 0x80, 0xF0, 0x90, 0xF0, # 6
            0xF0, 0x10, 0x20, 0x40, 0x40, # 7
            0xF0, 0x90, 0xF0, 0x90, 0xF0, # 8
            0xF0, 0x90, 0xF0, 0x10, 0xF0, # 9
            0xF0, 0x90, 0xF0, 0x90, 0x90, # A
            0xE0, 0x90, 0xE0, 0x90, 0xE0, # B
            0xF0, 0x80, 0x80, 0x80, 0xF0, # C
            0xE0, 0x90, 0x90, 0x90, 0xE0, # D
            0xF0, 0x80, 0xF0, 0x80, 0xF0, # E
            0xF0, 0x80, 0xF0, 0x80, 0x80  # F
        ]
        for i, byte in enumerate(self.font_set):
            self.memory[i] = byte
        self.halted = False
        self.running = True
        self.r = [0]*8
        self.waiting_for_key = None

    def load_rom(self, rom):
        """Loads a CHIP-8 ROM into memory starting at address 0x200."""
        with open(rom, "rb") as f:
            rom = f.read()
            for i, byte in enumerate(rom):
                self.memory[0x200 + i] = byte

    def cycle(self):
        if self.waiting_for_key is not None:
            for i in range(16):
                if self.key[i]:
                    self.v[self.waiting_for_key] = i
                    self.waiting_for_key = None
                    # advance past the Fx0A instruction (we backed up pc when
                    # entering waiting state)
                    self.pc += 2
                    break
            return

        # Fetch
        opcode = (self.memory[self.pc] << 8) | self.memory[self.pc + 1]
        self.pc += 2
        if opcode & 0x00FF == 0x00E0:
            # Clear screen
            self.gfx = [[0] * 64 for _ in range(32)]

        elif opcode & 0x00FF == 0x00EE:
            # Return from subroutine
            self.pc = self.stack.pop()

        elif opcode & 0xF000 == 0x1000:
            # Jump to address NNN
            self.pc = opcode & 0x0FFF

        elif opcode & 0xF000 == 0x2000:
            # Call subroutine at NNN
            self.stack.append(self.pc)
            self.pc = opcode & 0x0FFF

        elif opcode & 0xF000 == 0x3000:
            # Skip next instruction if Vx == NN
            x = (opcode & 0x0F00) >> 8
            nn = opcode & 0x00FF
            if self.v[x] == nn:
                self.pc += 2

        elif opcode & 0xF000 == 0x4000:
            # Skip next instruction if Vx != NN
            x = (opcode & 0x0F00) >> 8
            nn = opcode & 0x00FF
            if self.v[x] != nn:
                self.pc += 2

        elif opcode & 0xF000 == 0x5000:
            # Skip next instruction if Vx == Vy
            x = (opcode & 0x0F00) >> 8
            y = (opcode & 0x00F0) >> 4
            if self.v[x] == self.v[y]:
                self.pc += 2

        elif opcode & 0xF000 == 0x6000:
            # Set Vx = NN
            x = (opcode & 0x0F00) >> 8
            nn = opcode & 0x00FF
            self.v[x] = nn

        elif opcode & 0xF000 == 0x7000:
            # Set Vx = Vx + NN
            x = (opcode & 0x0F00) >> 8
            nn = opcode & 0x00FF
            self.v[x] = (self.v[x] + nn) & 0xFF

        elif opcode & 0xF00F == 0x8000:
            x = (opcode & 0x0F00) >> 8
            y = (opcode & 0x00F0) >> 4
            self.v[x] = self.v[y]

        elif opcode & 0xF00F == 0x8001:
            x = (opcode & 0x0F00) >> 8
            y = (opcode & 0x00F0) >> 4
            self.v[x] |= self.v[y]

        elif opcode & 0xF00F == 0x8002:
            x = (opcode & 0x0F00) >> 8
            y = (opcode & 0x00F0) >> 4
            self.v[x] &= self.v[y]

        elif opcode & 0xF00F == 0x8003:
            x = (opcode & 0x0F00) >> 8
            y = (opcode & 0x00F0) >> 4
            # Simply XOR the two register values and save to Vx
            self.v[x] ^= self.v[y]

        elif opcode & 0xF00F == 0x8004:
            x = (opcode & 0x0F00) >> 8
            y = (opcode & 0x00F0) >> 4
            if self.v[x] + self.v[y] > 0xFF:
                self.v[0xF] = 1
            else:
                self.v[0xF] = 0
            self.v[x] = (self.v[x] + self.v[y]) & 0xFF

        elif opcode & 0xF00F == 0x8005:
            x = (opcode & 0x0F00) >> 8
            y = (opcode & 0x00F0) >> 4
            if self.v[x] > self.v[y]:
                self.v[0xF] = 1
            else:
                self.v[0xF] = 0
            self.v[x] = (self.v[x] - self.v[y]) & 0xFF

        elif opcode & 0xF00F == 0x8006:
            x = (opcode & 0x0F00) >> 8
            y = (opcode & 0x00F0) >> 4
            if self.v[x] & 0x1:
                self.v[0xF] = 1
            else:
                self.v[0xF] = 0
            self.v[x] >>= 1

        elif opcode & 0xF00F == 0x8007:
            x = (opcode & 0x0F00) >> 8
            y = (opcode & 0x00F0) >> 4
            if self.v[y] > self.v[x]:
                self.v[0xF] = 1
            else:
                self.v[0xF] = 0
            self.v[x] = (self.v[y] - self.v[x]) & 0xFF

        elif opcode & 0xF00F == 0x800E:
            x = (opcode & 0x0F00) >> 8
            y = (opcode & 0x00F0) >> 4
            if self.v[x] & 0x80:
                self.v[0xF] = 1
            else:
                self.v[0xF] = 0
            self.v[x] = (self.v[x] << 1) & 0xFF

        elif opcode & 0xF000 == 0x9000:
            x = (opcode & 0x0F00) >> 8
            y = (opcode & 0x00F0) >> 4
            if self.v[x] != self.v[y]:
                self.pc += 2

        elif opcode & 0xF000 == 0xA000:
            nnn = opcode & 0x0FFF
            self.i = nnn

        elif opcode & 0xF000 == 0xB000:
            nnn = opcode & 0x0FFF
            self.i = nnn + self.v[0]

        elif opcode & 0xF000 == 0xC000:
            x = (opcode & 0x0F00) >> 8
            nn = opcode & 0x00FF
            self.v[x] = random.randint(0, 255) & nn

        elif opcode & 0xF000 == 0xD000:
            x_reg = (opcode & 0x0F00) >> 8
            y_reg = (opcode & 0x00F0) >> 4
            n = opcode & 0x000F
            self.v[0xF] = 0
            
            # Get the starting coordinates from the registers
            start_x = self.v[x_reg]
            start_y = self.v[y_reg]
            
            for row in range(n):
                sprite_byte = self.memory[self.i + row]
                for col in range(8):
                    if sprite_byte & (0x80 >> col):
                        # Wrap coordinates using modulo so they stay on screen
                        screen_x = (start_x + col) % 64
                        screen_y = (start_y + row) % 32
                        
                        if self.gfx[screen_y][screen_x]:
                            self.v[0xF] = 1
                        self.gfx[screen_y][screen_x] ^= 1

        elif opcode & 0xF000 == 0xE000:
            x = (opcode & 0x0F00) >> 8
            if opcode & 0x00FF == 0x9E:
                # Skip next instruction if key with the value of Vx is pressed
                if self.key[self.v[x]]:
                    self.pc += 2
            elif opcode & 0x00FF == 0xA1:
                # Skip next instruction if key with the value of Vx is not pressed
                if not self.key[self.v[x]]:
                    self.pc += 2

        elif opcode & 0xF0FF == 0xF007:
            x = (opcode & 0x0F00) >> 8
            self.v[x] = self.delay_timer

        elif opcode & 0xF0FF == 0xF00A:
            x = (opcode & 0x0F00) >> 8
            self.v[x] = self.delay_timer
            self.waiting_for_key = x
            # back up pc so we can re-execute this instruction after key press
            self.pc -= 2

        elif opcode & 0xF0FF == 0xF015:
            x = (opcode & 0x0F00) >> 8
            self.delay_timer = self.v[x]

        elif opcode & 0xF0FF == 0xF018:
            x = (opcode & 0x0F00) >> 8
            self.sound_timer = self.v[x]

        elif opcode & 0xF0FF == 0xF01E:
            x = (opcode & 0x0F00) >> 8
            self.i = (self.i + self.v[x]) & 0xFFFF

        elif opcode & 0xF0FF == 0xF029:
            x = (opcode & 0x0F00) >> 8
            self.i = self.v[x] * 5

        elif opcode & 0xF0FF == 0xF033:
            x = (opcode & 0x0F00) >> 8
            self.memory[self.i] = self.v[x] // 100
            self.memory[self.i + 1] = (self.v[x] // 10) % 10
            self.memory[self.i + 2] = self.v[x] % 10
            
        elif opcode & 0xF0FF == 0xF055:
            x = (opcode & 0x0F00) >> 8
            for i in range(x + 1):
                self.memory[self.i + i] = self.v[i]
                
        elif opcode & 0xF0FF == 0xF065:
            x = (opcode & 0x0F00) >> 8
            for i in range(x + 1):
                self.v[i] = self.memory[self.i + i]

        else:
            # if opcode != 0:
            print(f"Unknown opcode: {opcode:04X} at PC: {self.pc-2:04X}")

class EmulatorApp:
    """Main application class that sets up the GUI, handles user interactions,
    and runs the emulator loop in a separate thread."""
    def __init__(self):
        self.root = tk.Tk()
        self.chip = None
        self.emu_thread = None
        self.key_map = {
            pygame.K_1: 0x1, pygame.K_2: 0x2, pygame.K_3: 0x3, pygame.K_4: 0xC,
            pygame.K_q: 0x4, pygame.K_w: 0x5, pygame.K_e: 0x6, pygame.K_r: 0xD,
            pygame.K_a: 0x7, pygame.K_s: 0x8, pygame.K_d: 0x9, pygame.K_f: 0xE,
            pygame.K_z: 0xA, pygame.K_x: 0x0, pygame.K_c: 0xB, pygame.K_v: 0xF,
        }

        fp_btn = tk.Button(self.root, text="Load ROM", command=self.file_picker)
        fp_btn.pack()
        halt_btn = tk.Button(self.root, text="Halt Emulation", command=self.halt_emu)
        halt_btn.pack()
        unhalt_btn = tk.Button(self.root, text="Unhalt Emulation", command=self.unhalt_emu)
        unhalt_btn.pack()

    def start_emulator(self, rom_path):
        """Starts the emulator with the given ROM path.
        If an emulator instance is already running, it will be stopped first."""
        # Stop any previous instance
        if self.chip is not None:
            self.chip.running = False
        if self.emu_thread is not None and self.emu_thread.is_alive():
            self.emu_thread.join()

        # Start new emulator
        self.chip = Chip8()
        try:
            self.chip.load_rom(rom_path)
        except FileNotFoundError:
            print(f"ROM not found: {rom_path}")
            self.chip = None
            return
        self.emu_thread = threading.Thread(target=self.main)
        self.emu_thread.daemon = True
        self.emu_thread.start()

    def file_picker(self):
        """Opens a file dialog to select a ROM, and starts the emulator with the selected ROM.
        If no ROM is selected, it attempts to load a default PONG.ch8 ROM as a fallback."""
        rom = askopenfilename()
        if rom:
            self.start_emulator(rom)
        else:
            try:
                rom = "roms/PONG.ch8"
                self.start_emulator(rom)
            except FileNotFoundError:
                print("PONG.ch8 not found, no fallback")

    def halt_emu(self):
        """Halts (pauses) the emulator. If the emulator is not running, it will show a message."""
        if self.chip is not None:
            self.chip.halted = True
            print("Emulator halted (paused)")
        else:
            print("Emulator not started, nothing to halt...")

    def unhalt_emu(self):
        """Unhalts (resumes) the emulator.
        If the emulator is not running, it will show a message."""
        if self.chip is not None and self.emu_thread is not None and not self.emu_thread.is_alive():
            print("Emulator thread is not running. Please load a ROM to restart.")
        elif self.chip is not None and self.emu_thread is not None and self.emu_thread.is_alive():
            self.chip.halted = False
            print("Emulator unhalted (resumed)")
        else:
            print("Emulator not started, nothing to unhalt...")
    def main(self):
        pygame.init()
        window = pygame.display.set_mode((640, 320))  # 10x scale
        clock = pygame.time.Clock()
        try:
            pygame.mixer.init()
            try:
                beep = pygame.mixer.Sound("tone.wav")
            except Exception:
                beep = None
        except Exception:
            beep = None
        pygame.display.set_caption("CHIP-8")
        try:
            while self.chip and self.chip.running:
                if self.chip.halted:
                    time.sleep(0.01)
                    continue

                self.chip.cycle()
                if random.randint(1, 4) == 1: 
                    if self.chip.delay_timer > 0:
                        self.chip.delay_timer -= 1
                    if self.chip.sound_timer > 0:
                        self.chip.sound_timer -= 1

                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.chip.halted = True
                        self.chip.running = False
                        pygame.quit()
                        sys.exit()
                    elif event.type == pygame.KEYDOWN:
                        if event.key in self.key_map:
                            self.chip.key[self.key_map[event.key]] = 1
                    elif event.type == pygame.KEYUP:
                        if event.key in self.key_map:
                            self.chip.key[self.key_map[event.key]] = 0

                if self.chip.sound_timer > 0 and beep:
                    try:
                        beep.play()
                    except Exception:
                        pass

                if self.chip.waiting_for_key is not None:
                    time.sleep(0.01)

                window.fill((0, 0, 0))
                for y in range(32):
                    for x in range(64):
                        if self.chip.gfx[y][x]:
                            pygame.draw.rect(window, (255, 255, 255), (x*10, y*10, 10, 10))
                pygame.display.flip()

                clock.tick(240)
        finally:
            try:
                pygame.mixer.quit()
            except Exception:
                pass
            try:
                pygame.quit()
            except Exception:
                pass

if __name__ == "__main__":
    app = EmulatorApp()
    app.root.mainloop()

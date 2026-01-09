import pygame
import sys
import random
import tkinter as tk
from tkinter import messagebox
from tkinter.filedialog import askopenfilename
import threading

root = tk.Tk()

key_map = {
    pygame.K_1: 0x1, pygame.K_2: 0x2, pygame.K_3: 0x3, pygame.K_4: 0xC,
    pygame.K_q: 0x4, pygame.K_w: 0x5, pygame.K_e: 0x6, pygame.K_r: 0xD,
    pygame.K_a: 0x7, pygame.K_s: 0x8, pygame.K_d: 0x9, pygame.K_f: 0xE,
    pygame.K_z: 0xA, pygame.K_x: 0x0, pygame.K_c: 0xB, pygame.K_v: 0xF,
}

# Global reference to the running emulator thread and chip instance
emu_thread = None
chip = None

class Chip8:
    def __init__(self):
        self.memory = [0] * 4096
        self.V = [0] * 16
        self.I = 0
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
        for i in range(len(self.font_set)):
            self.memory[i] = self.font_set[i]
        self.halted = False
        self.R = [0]*8
        self.resMode = "low"

    def load_rom(self, rom):
        with open(rom, "rb") as f:
            rom = f.read()
            for i, byte in enumerate(rom):
                self.memory[0x200 + i] = byte

    def cycle(self):
        # Fetch
        opcode = (self.memory[self.pc] << 8) | self.memory[self.pc + 1]
        self.pc += 2
        # Decode + Execute (simplified example)
        if opcode & 0xF000 == 0x6000:  # 6XNN: set VX = NN
            # Matches 6XNN: Set Vx = NN
            x = (opcode & 0x0F00) >> 8
            nn = opcode & 0x00FF
            self.V[x] = nn
        elif opcode == 0x00E0:  # Clear screen
            # Matches 00E0: Clear the display
            self.gfx = [[0] * 64 for _ in range(32)]
        elif opcode & 0xF000 == 0x3000:
            # Matches 3XNN: Skip next instruction if Vx == NN
            x = (opcode & 0x0F00) >> 8
            nn = opcode & 0x00FF
            if self.V[x] == nn:
                self.pc += 2  # Skip the next instruction
        elif opcode & 0xF000 == 0x2000:  # 2NNN: call subroutine at NNN
            # Matches 2NNN: Call subroutine at address NNN
            nnn = opcode & 0x0FFF
            if len(self.stack) < 16:
                self.stack.append(self.pc)
                self.pc = nnn
            else:
                print("Stack overflow!")
                self.halted = True
                self.show_message("Halted!", "Emulator halted due to stack overflow!")
            self.pc = nnn
        elif opcode & 0xF000 == 0xA000:  # ANNN: set I = NNN
            # Matches ANNN: Set I = NNN
            nnn = opcode & 0x0FFF
            self.I = nnn
        elif opcode & 0xF000 == 0xD000:  # DXYN: draw sprite
            # Matches DXYN: Draw sprite at (Vx, Vy) with N bytes of sprite data
            x = self.V[(opcode & 0x0F00) >> 8]
            y = self.V[(opcode & 0x00F0) >> 4]
            height = opcode & 0x000F
            self.V[0xF] = 0
            for row in range(height):
                pixel = self.memory[self.I + row]
                for col in range(8):
                    if (pixel & (0x80 >> col)) != 0:
                        if self.gfx[(y + row) % 32][(x + col) % 64] == 1:
                            self.V[0xF] = 1
                        self.gfx[(y + row) % 32][(x + col) % 64] ^= 1
        elif opcode & 0xF000 == 0x7000:  # 7XNN: add NN to VX
            # Matches 7XNN: Add NN to Vx
            x = (opcode & 0x0F00) >> 8
            nn = opcode & 0x00FF
            self.V[x] = (self.V[x] + nn) & 0xFF
        elif opcode & 0xF000 == 0x1000:  # 1NNN: jump to address NNN
            # Matches 1NNN: Jump to address NNN
            nnn = opcode & 0x0FFF
            self.pc = nnn
        elif opcode & 0xF000 == 0x0000 and opcode & 0x00FF == 0xEE:  # 00EE: return from subroutine
            # Matches 00EE: Return from subroutine
            if self.stack:
                self.pc = self.stack.pop()
            else:
                print("Stack underflow!")
                self.halted = True
                self.show_message("Halted!", "Emulator halted due to stack underflow!")
        elif opcode & 0xF000 == 0xF000 and opcode & 0x00FF == 0x33:  # Fx33: LD B, Vx
            # Matches Fx33: Store BCD of Vx at I, I+1, I+2
            x = (opcode & 0x0F00) >> 8
            value = self.V[x]
            self.memory[self.I]     = value // 100         # Hundreds digit
            self.memory[self.I + 1] = (value // 10) % 10   # Tens digit
            self.memory[self.I + 2] = value % 10           # Ones digit
        elif opcode & 0xF000 == 0xF000 and opcode & 0x00FF == 0x65: # read Read registers V0 through Vx from memory starting at address I.
            # Matches Fx65: Read registers V0 through Vx from memory starting at I
            x = (opcode & 0x0F00) >> 8
            for i in range(x + 1):
                self.V[i] = self.memory[self.I + i]

        elif opcode & 0xF000 == 0xF000 and opcode & 0x00FF == 0x29:
            # Matches Fx29: Set I to location of sprite for digit Vx
            x = (opcode & 0x0F00) >> 8
            self.I = self.V[x] * 5  # Each font sprite is 5 bytes

        elif opcode & 0xF000 == 0xF000 and opcode & 0x00FF == 0x07:
            # Matches Fx07: Set Vx = delay timer
            x = (opcode & 0x0F00) >> 8
            self.V[x] = self.delay_timer

        elif opcode & 0xF000 == 0xF000 and opcode & 0x00FF == 0x15:
            # Matches Fx15: Set delay timer = Vx
            x = (opcode & 0x0F00) >> 8
            self.delay_timer = self.V[x]

        elif opcode & 0xF0FF == 0xE0A1:
            # Matches ExA1: Skip next instruction if key[Vx] is not pressed
            x = (opcode & 0x0F00) >> 8
            if not self.key[self.V[x]]:
                self.pc += 2

        elif opcode & 0xF0FF == 0xE09E:
            # Matches Ex9E: Skip next instruction if key[Vx] is pressed
            x = (opcode & 0x0F00) >> 8
            if self.key[self.V[x]]:
                self.pc += 2

        elif opcode & 0xF000 == 0xC000:
            # Matches CXNN: Set Vx = random byte & NN
            x = (opcode & 0x0F00) >> 8
            kk = opcode & 0x00FF 
            self.V[x] = random.randint(0, 255) & kk

        elif opcode & 0xF00F == 0x8002:
            # Matches 8XY2: Set Vx = Vx & Vy
            x = (opcode & 0x0F00) >> 8
            y = (opcode & 0x00F0) >> 4
            self.V[x] = self.V[x] & self.V[y]

        elif opcode & 0xF00F == 0x8004:
            # Matches 8XY4: Set Vx = Vx + Vy, set VF = carry
            x = (opcode & 0x0F00) >> 8
            y = (opcode & 0x00F0) >> 4
            result = self.V[x] + self.V[y]
            self.V[0xF] = 1 if result > 0xFF else 0
            self.V[x] = result & 0xFF

        elif opcode & 0xF000 == 0x4000:
            # Matches 4XNN: Skip next instruction if Vx != NN
            x = (opcode & 0x0F00) >> 8
            kk = opcode & 0x00FF 
            if self.V[x] != kk:
                self.pc += 2  # Skip next instruction
        
        elif opcode & 0xF00F == 0x8000:
            # Matches 8xyN: Copy Y to X so (x = y)
            x = (opcode & 0x0F00) >> 8
            y = (opcode & 0x00F0) >> 4
            self.V[x] = self.V[y]

        elif opcode & 0xF00F == 0x8005:
            # Matches 8xy5: Subtract X from Y
            x = (opcode & 0x0F00) >> 8
            y = (opcode & 0x00F0) >> 4
            self.V[0xF] = 1 if self.V[x] >= self.V[y] else 0
            self.V[x] = (self.V[x] - self.V[y]) & 0xFF
            
        elif opcode & 0xF0FF == 0xF018:
            # Matches Fx18: copies x to sound_timer
            x = (opcode & 0x0F00) >> 8
            self.sound_timer = self.V[x]
        
        elif opcode & 0xF00F == 0x5000:
            x = (opcode & 0x0F00) >> 8
            y = (opcode & 0x00F0) >> 4
            if self.V[x] == self.V[y]:
                self.pc += 2

        elif opcode & 0xF00F == 0x8006:
            # Matches 8xy6: Set Vx = Vx >> 1, VF = least significant bit of Vx before shift
            x = (opcode & 0x0F00) >> 8
            self.V[0xF] = self.V[x] & 0x1
            self.V[x] = self.V[x] >> 1

        elif opcode & 0xF00F == 0x8007:
            # Matches 8xy7: Set Vx = Vy - Vx, VF = 1 if Vy > Vx else 0
            x = (opcode & 0x0F00) >> 8
            y = (opcode & 0x00F0) >> 4
            self.V[0xF] = 1 if self.V[y] > self.V[x] else 0
            self.V[x] = (self.V[y] - self.V[x]) & 0xFF

        elif opcode & 0xF00F == 0x800E:
            # Matches 8xyE: Set Vx = Vx << 1, VF = most significant bit of Vx before shift
            x = (opcode & 0x0F00) >> 8
            self.V[0xF] = (self.V[x] & 0x80) >> 7
            self.V[x] = (self.V[x] << 1) & 0xFF

        elif opcode & 0xF00F == 0x9000:
            # Matches 9xy0: Skip next instruction if Vx != Vy
            x = (opcode & 0x0F00) >> 8
            y = (opcode & 0x00F0) >> 4
            if self.V[x] != self.V[y]:
                self.pc += 2
            else:
                pass
        
        elif opcode & 0xF0FF == 0xF00A:
            # Matches Fx0A: Wait until key press (key is x)
            x = (opcode & 0x0F00) >> 8
            key_pressed = False
            for i in range(16):
                if self.key[i]:
                    self.V[x] = i
                    key_pressed = True
                    break
            if not key_pressed:
                self.pc -= 2  # Repeat this instruction until a key is pressed
        
        elif opcode & 0xF0FF == 0xF01E:
            # Matches Fx1E: Adds x to I
            x = (opcode & 0x0F00) >> 8
            self.I = (self.I + self.V[x]) & 0xFFFF  # I is 12 bits, but 16 is safe
        
        elif opcode & 0xF0FF == 0xF055:
            # Matches Fx55: Store V0 to Vx in memory starting at I
            x = (opcode & 0x0F00) >> 8
            for i in range(x + 1):
                self.memory[self.I + i] = self.V[i]

        elif opcode & 0xF00F == 0x8001:
            # Matches 8xy1: Set Vx = Vx | Vy (bitwise OR)
            x = (opcode & 0x0F00) >> 8
            y = (opcode & 0x00F0) >> 4
            self.V[x] = self.V[x] | self.V[y]

        elif opcode & 0xF00F == 0x8003:
            # Matches 8xy3: Set Vx = Vx ^ Vy (bitwise XOR)
            x = (opcode & 0x0F00) >> 8
            y = (opcode & 0x00F0) >> 4
            self.V[x] = self.V[x] ^ self.V[y]

        elif opcode & 0xF000 == 0xB000:
            # Matches BNNN: Jump to address NNN + V0
            nnn = opcode & 0x0FFF
            self.pc = nnn + self.V[0]

        elif opcode & 0xF0FF == 0xF075:
            # Matches Fx75: Load Vx into R
            x = (opcode & 0x0F00) >> 8
            for i in range(x + 1):
                self.R[i] = self.V[i]
        
        elif opcode & 0xF0FF == 0xF085:
            # Fx85: Load V0..Vx from R[0..x]
            x = (opcode & 0x0F00) >> 8
            for i in range(x + 1):
                self.V[i] = self.R[i]

        elif opcode & 0x00FF == 0x00FD:
            sys.exit()

        elif opcode & 0x00FF == 0x00FE:
            self.resMode = "low"
        
        elif opcode & 0x00FF == 0x00FF:
            self.resMode = "high"

        elif opcode & 0x00FF == 0x00CF:
            # Matches 00CN: moves screen down by N
            n = (opcode & 0x000F) >> 8
            height = len(self.gfx)
            width = len(self.gfx[0])
            self.gfx[n:] = self.gfx[:-n]  # move all rows down by n
            for i in range(n):
                self.gfx[i] = [0] * width

        elif opcode & 0x00FF == 0x00FB:
            # Matches 00FB: moves screen left by 4
            for row in self.gfx:
                row[4:] = row[:-4]  # move pixels right by 4
                row[:4] = [0] * 4   # clear leftmost 4 pixels

        elif opcode & 0x00FF == 0x00FC:
            # Matches 00FC: moves screen right by 4
            for row in self.gfx:
                row[:-4] = row[4:]  # move pixels left by 4
                row[-4:] = [0] * 4  # clear rightmost 4 pixels

        else:
            print(f"Unknown opcode: {opcode:04X}")

        # Update timers
        if self.delay_timer > 0:
            self.delay_timer -= 1
        if self.sound_timer > 0:
            self.sound_timer -= 1

    def show_message(self, title, text):
        messagebox.showinfo(title, text)

def start_emulator(rom_path):
    global emu_thread, chip
    # If an emulator is already running, halt it and wait for thread to finish
    if chip is not None:
        chip.halted = True
        if emu_thread is not None:
            emu_thread.join()
    # Create a new Chip8 instance and start the emulator thread
    chip = Chip8()
    chip.load_rom(rom_path)
    emu_thread = threading.Thread(target=main, args=(chip,))
    emu_thread.daemon = True
    emu_thread.start()

def stop_emulator():
    pass  # Not needed; handled by halted flag

def file_picker():
    rom = askopenfilename()
    if rom:
        start_emulator(rom)
    else:
        rom = "roms/PONG.ch8"
        start_emulator(rom)

def halt_emu():
    global chip
    if chip is not None:
        chip.halted = True

def main(chip):
    pygame.init()
    window = pygame.display.set_mode((640, 320))  # 10x scale
    clock = pygame.time.Clock()
    pygame.mixer.init()
    pygame.display.set_caption("CHIP-8")
    beep = pygame.mixer.Sound("tone.wav")

    while not chip.halted:
        chip.cycle()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                chip.halted = True
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key in key_map:
                    chip.key[key_map[event.key]] = 1
            elif event.type == pygame.KEYUP:
                if event.key in key_map:
                    chip.key[key_map[event.key]] = 0
        
        if chip.sound_timer > 0:
            beep.play()

        # Draw graphics
        window.fill((0, 0, 0))
        if chip.resMode == "low":
            for y in range(32):
                for x in range(64):
                    if chip.gfx[y][x]:
                        pygame.draw.rect(window, (255, 255, 255), (x*10, y*10, 10, 10))
        else:
            for y in range(64):
                for x in range(128):
                    if chip.gfx[y][x]:
                        pygame.draw.rect(window, (255, 255, 255), (x*10, y*10, 10, 10))
        pygame.display.flip()

        clock.tick(240)

if __name__ == "__main__":
    fpBtn = tk.Button(root, text="Load ROM", command=file_picker)
    fpBtn.pack()
    haltBtn = tk.Button(root, text="Halt Emulation", command=halt_emu)
    haltBtn.pack()
    root.mainloop()

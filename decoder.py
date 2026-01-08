with open("roms/rps.ch8", "rb") as f:
    rom = f.read()
    for i in range(0, len(rom), 2):
        opcode = (rom[i] << 8) | rom[i+1]
        print(f"{i+0x200:04X}: {opcode:04X}")
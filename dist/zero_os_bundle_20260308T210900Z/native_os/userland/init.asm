; Zero OS userland init module placeholder (flat binary payload)
bits 32
org 0x0

start:
    mov eax, 0x1
    mov ebx, 0x0
.hang:
    nop
    jmp .hang

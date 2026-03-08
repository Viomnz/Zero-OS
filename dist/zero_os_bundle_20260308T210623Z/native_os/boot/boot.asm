; Zero OS Native Boot Sector (x86 real mode, BIOS)
; Loads stage2 from sectors 2..(2+STAGE2_SECTORS-1) to 0000:8000 and jumps.
bits 16
org 0x7C00

STAGE2_LOAD_SEG equ 0x0000
STAGE2_LOAD_OFF equ 0x8000
STAGE2_SECTORS  equ 4

start:
    cli
    xor ax, ax
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov sp, 0x7C00
    sti

    mov [boot_drive], dl

    xor ax, ax
    mov es, ax
    mov bx, STAGE2_LOAD_OFF

    mov ah, 0x02          ; BIOS read sectors
    mov al, STAGE2_SECTORS
    mov ch, 0x00          ; cylinder 0
    mov cl, 0x02          ; sector 2 (1-based)
    mov dh, 0x00          ; head 0
    mov dl, [boot_drive]  ; boot drive
    int 0x13
    jc disk_error

    jmp STAGE2_LOAD_SEG:STAGE2_LOAD_OFF

disk_error:
    mov si, err_msg
    call print_str
    jmp $

print_str:
    lodsb
    test al, al
    jz .done
    mov ah, 0x0E
    mov bh, 0x00
    mov bl, 0x0C
    int 0x10
    jmp print_str
.done:
    ret

boot_drive db 0
err_msg db "Zero OS boot error: disk read fail", 0

times 510-($-$$) db 0
dw 0xAA55

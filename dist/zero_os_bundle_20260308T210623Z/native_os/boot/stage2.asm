; Zero OS Stage-2 Loader Skeleton
; Real mode loader for kernel + protected mode handoff.
bits 16
org 0x8000

KERNEL_LOAD_SEG equ 0x1000
KERNEL_LOAD_OFF equ 0x0000
KERNEL_START_SECTOR equ 6
KERNEL_SECTORS equ 64

start:
    cli
    xor ax, ax
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov sp, 0x9000
    sti

    mov si, msg_stage2
    call print_str

    ; Load kernel payload before switching modes.
    mov ax, KERNEL_LOAD_SEG
    mov es, ax
    mov bx, KERNEL_LOAD_OFF
    mov ch, 0x00
    mov cl, KERNEL_START_SECTOR
    mov dh, 0x00
    mov dl, 0x00
    mov si, KERNEL_SECTORS
.read_loop:
    mov ah, 0x02
    mov al, 0x01
    int 0x13
    jc kernel_load_fail
    add bx, 512
    cmp bx, 0x0000
    jne .next_sector
    mov ax, es
    add ax, 0x1000
    mov es, ax
.next_sector:
    inc cl
    cmp cl, 19
    jne .next_chs
    mov cl, 1
    inc dh
    cmp dh, 2
    jne .next_chs
    mov dh, 0
    inc ch
.next_chs:
    dec si
    jnz .read_loop

    cli
    lgdt [gdt_desc]
    mov eax, cr0
    or eax, 1
    mov cr0, eax
    jmp 0x08:pmode_entry

kernel_load_fail:
    mov si, msg_kernel_fail
    call print_str
    jmp $

print_str:
    lodsb
    test al, al
    jz .done
    mov ah, 0x0E
    mov bh, 0x00
    mov bl, 0x07
    int 0x10
    jmp print_str
.done:
    ret

msg_stage2 db "Zero OS Stage2 loaded", 0
msg_kernel_fail db "Kernel load failed", 0

align 8
gdt_start:
    dq 0x0000000000000000
    dq 0x00CF9A000000FFFF  ; code
    dq 0x00CF92000000FFFF  ; data
gdt_end:

gdt_desc:
    dw gdt_end - gdt_start - 1
    dd gdt_start

bits 32
pmode_entry:
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov fs, ax
    mov gs, ax
    mov ss, ax
    mov esp, 0x9FC00
    jmp dword 0x00010000

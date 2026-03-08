; Zero OS Kernel Entry (32-bit protected mode)
; Includes scaffolding for:
; - paging + virtual memory
; - user/kernel mode separation primitives
; - syscall gateway (int 0x80)
; - scheduler context-switch hooks
; - physical/virtual allocator integration
bits 32
org 0x10000

KERNEL_CODE_SEL equ 0x08
KERNEL_DATA_SEL equ 0x10
USER_CODE_SEL   equ 0x1B
USER_DATA_SEL   equ 0x23

start32:
    cli
    call init_gdt
    call init_segments
    call init_paging
    call init_idt
    call remap_pic
    call init_pit
    call init_syscalls
    call init_mm
    call init_scheduler

    sti
    call kmain

.idle:
    hlt
    jmp .idle

kmain:
    mov dword [0xB8000], 0x1F4B1F5A ; 'ZK'
    mov dword [0xB8004], 0x1F4D1F4D ; 'MM'
    mov dword [0xB8008], 0x1F56501F ; 'PV'
    ret

; --------------------------
; Mode and segmentation
; --------------------------
init_gdt:
    lgdt [gdt_desc]
    ret

init_segments:
    mov ax, KERNEL_DATA_SEL
    mov ds, ax
    mov es, ax
    mov fs, ax
    mov gs, ax
    mov ss, ax
    mov esp, 0x9E000
    ret

; --------------------------
; Paging + alloc integration
; --------------------------
init_paging:
    ; Build identity map for first 4 MiB.
    mov ecx, 1024
    xor edi, edi
.pt_loop:
    mov eax, edi
    shl eax, 12
    or eax, 0x003                ; present + rw
    mov [page_table_0 + edi*4], eax
    inc edi
    loop .pt_loop

    mov eax, page_table_0
    or eax, 0x003
    mov [page_directory + 0], eax

    ; Mark page 0 unavailable in physical bitmap.
    mov dword [phys_bitmap + 0], 1

    mov eax, page_directory
    mov cr3, eax
    mov eax, cr0
    or eax, 0x80000000           ; PG on
    mov cr0, eax
    ret

init_mm:
    ; Example allocation path: reserve one page for kernel heap head.
    call alloc_phys_page
    mov [kernel_heap_page], eax
    ret

alloc_phys_page:
    ; very small linear allocator bitmap: 4096 pages max
    mov ecx, 4096
    xor ebx, ebx
.find_free:
    cmp dword [phys_bitmap + ebx*4], 0
    je .claim
    inc ebx
    loop .find_free
    mov eax, 0xFFFFFFFF
    ret
.claim:
    mov dword [phys_bitmap + ebx*4], 1
    mov eax, ebx
    shl eax, 12
    ret

free_phys_page:
    ; in: eax = physical address aligned to 4KiB
    mov ebx, eax
    shr ebx, 12
    cmp ebx, 4095
    ja .bad
    mov dword [phys_bitmap + ebx*4], 0
    mov eax, 1
    ret
.bad:
    xor eax, eax
    ret

map_page:
    ; in: eax=virt, ebx=phys, ecx=flags
    ; prototype maps only first page table region.
    mov edx, eax
    shr edx, 12
    and edx, 0x3FF
    and ebx, 0xFFFFF000
    or ebx, ecx
    or ebx, 0x001                  ; present
    mov [page_table_0 + edx*4], ebx
    invlpg [eax]
    mov eax, 1
    ret

; --------------------------
; Interrupts + syscalls
; --------------------------
init_idt:
    lea eax, [idt]
    mov dword [idtr + 2], eax
    mov word [idtr], idt_end - idt - 1
    lidt [idtr]
    ret

set_gate:
    ; in: eax=handler, ebx=vector, cl=type_attr
    mov edx, ebx
    shl edx, 3
    mov word [idt + edx + 0], ax
    mov word [idt + edx + 2], KERNEL_CODE_SEL
    mov byte [idt + edx + 4], 0
    mov byte [idt + edx + 5], cl
    shr eax, 16
    mov word [idt + edx + 6], ax
    ret

init_syscalls:
    mov eax, irq0_handler
    mov ebx, 32
    mov cl, 10001110b              ; ring0 interrupt gate
    call set_gate

    mov eax, syscall_handler
    mov ebx, 128
    mov cl, 11101110b              ; DPL=3 interrupt gate for user programs
    call set_gate
    ret

remap_pic:
    mov al, 0x11
    out 0x20, al
    out 0xA0, al
    mov al, 0x20
    out 0x21, al
    mov al, 0x28
    out 0xA1, al
    mov al, 0x04
    out 0x21, al
    mov al, 0x02
    out 0xA1, al
    mov al, 0x01
    out 0x21, al
    out 0xA1, al
    mov al, 11111110b              ; unmask IRQ0 only
    out 0x21, al
    mov al, 11111111b
    out 0xA1, al
    ret

init_pit:
    mov al, 00110110b
    out 0x43, al
    mov ax, 11932                  ; ~100 Hz
    out 0x40, al
    mov al, ah
    out 0x40, al
    ret

irq0_handler:
    pushad
    inc dword [tick_count]
    call schedule_next
    mov eax, [tick_count]
    and eax, 0x0000000F
    add eax, '0'
    mov [0xB8002], al
    mov byte [0xB8003], 0x1F
    mov al, 0x20
    out 0x20, al
    popad
    iretd

syscall_handler:
    pushad
    ; syscall number in eax (saved at [esp + 28] after pushad)
    mov eax, [esp + 28]
    cmp eax, 1
    je .sys_alloc_page
    cmp eax, 2
    je .sys_free_page
    jmp .sys_unknown
.sys_alloc_page:
    call alloc_phys_page
    mov [esp + 28], eax
    jmp .done
.sys_free_page:
    mov eax, [esp + 32]            ; arg0 from caller-convention placeholder
    call free_phys_page
    mov [esp + 28], eax
    jmp .done
.sys_unknown:
    mov dword [esp + 28], 0xFFFFFFFF
.done:
    popad
    iretd

; --------------------------
; Scheduler context switching
; --------------------------
init_scheduler:
    mov dword [current_task], 0
    mov dword [task_count], 2
    mov dword [task_esp + 0], 0x9D000
    mov dword [task_esp + 4], 0x9C000
    ret

schedule_next:
    ; prototype round-robin task slot rotate.
    mov eax, [current_task]
    inc eax
    cmp eax, [task_count]
    jb .ok
    xor eax, eax
.ok:
    mov [current_task], eax
    ; real switch would save/restore full context + cr3 per process.
    ret

; --------------------------
; Data tables
; --------------------------
align 8
gdt:
    dq 0x0000000000000000
    dq 0x00CF9A000000FFFF           ; 0x08 kernel code
    dq 0x00CF92000000FFFF           ; 0x10 kernel data
    dq 0x00CFFA000000FFFF           ; 0x18 user code
    dq 0x00CFF2000000FFFF           ; 0x20 user data
gdt_end:

gdt_desc:
    dw gdt_end - gdt - 1
    dd gdt

align 8
idtr:
    dw 0
    dd 0

align 16
idt:
    times 256 dq 0
idt_end:

align 4096
page_directory:
    times 1024 dd 0

align 4096
page_table_0:
    times 1024 dd 0

align 16
phys_bitmap:
    times 4096 dd 0

kernel_heap_page dd 0
tick_count dd 0
current_task dd 0
task_count dd 0
task_esp times 8 dd 0

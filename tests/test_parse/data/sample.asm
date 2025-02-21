section .data
    hello db 'Hello, World!', 0
    fmt db '%s', 10, 0

section .text
    global main
    extern printf

main:
    push rbp
    mov rbp, rsp
    
    ; Print hello message
    mov rdi, fmt
    mov rsi, hello
    xor eax, eax
    call printf
    
    mov rsp, rbp
    pop rbp
    ret 
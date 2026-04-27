"""Windows console scan-code -> ANSI escape sequence mapping.

msvcrt.getch() returns two-byte sequences for special keys on Windows.
The first byte is a prefix (0x00 or 0xE0) and the second is the scan code.
Linux guests expect standard ANSI/VT sequences; this table provides the translation.
"""

WIN_SCANCODES: dict[tuple[int, int], bytes] = {
    # Plain arrows / navigation
    (0xE0, 0x48): b"\x1b[A",  # Up
    (0xE0, 0x50): b"\x1b[B",  # Down
    (0xE0, 0x4B): b"\x1b[D",  # Left
    (0xE0, 0x4D): b"\x1b[C",  # Right
    (0xE0, 0x47): b"\x1b[H",  # Home
    (0xE0, 0x4F): b"\x1b[F",  # End
    (0xE0, 0x52): b"\x1b[2~",  # Insert
    (0xE0, 0x53): b"\x1b[3~",  # Delete
    (0xE0, 0x49): b"\x1b[5~",  # Page Up
    (0xE0, 0x51): b"\x1b[6~",  # Page Down
    # Extra navigation
    (0x00, 0x0F): b"\x1b[Z",  # Shift+Tab
    # Ctrl+arrows (word movement in readline/editors)
    (0xE0, 0x8D): b"\x1b[1;5A",  # Ctrl+Up
    (0xE0, 0x91): b"\x1b[1;5B",  # Ctrl+Down
    (0xE0, 0x73): b"\x1b[1;5D",  # Ctrl+Left
    (0xE0, 0x74): b"\x1b[1;5C",  # Ctrl+Right
    # Ctrl+navigation
    (0xE0, 0x77): b"\x1b[1;5H",  # Ctrl+Home
    (0xE0, 0x75): b"\x1b[1;5F",  # Ctrl+End
    (0xE0, 0x92): b"\x1b[2;5~",  # Ctrl+Insert
    (0xE0, 0x93): b"\x1b[3;5~",  # Ctrl+Delete
    (0xE0, 0x84): b"\x1b[5;5~",  # Ctrl+Page Up
    (0xE0, 0x76): b"\x1b[6;5~",  # Ctrl+Page Down
    # Function keys
    (0x00, 0x3B): b"\x1bOP",  # F1
    (0x00, 0x3C): b"\x1bOQ",  # F2
    (0x00, 0x3D): b"\x1bOR",  # F3
    (0x00, 0x3E): b"\x1bOS",  # F4
    (0x00, 0x3F): b"\x1b[15~",  # F5
    (0x00, 0x40): b"\x1b[17~",  # F6
    (0x00, 0x41): b"\x1b[18~",  # F7
    (0x00, 0x42): b"\x1b[19~",  # F8
    (0x00, 0x43): b"\x1b[20~",  # F9
    (0x00, 0x44): b"\x1b[21~",  # F10
    (0xE0, 0x85): b"\x1b[23~",  # F11
    (0xE0, 0x86): b"\x1b[24~",  # F12
    # Ctrl + Function keys
    (0x00, 0x5E): b"\x1b[1;5P",  # Ctrl+F1
    (0x00, 0x5F): b"\x1b[1;5Q",  # Ctrl+F2
    (0x00, 0x60): b"\x1b[1;5R",  # Ctrl+F3
    (0x00, 0x61): b"\x1b[1;5S",  # Ctrl+F4
    (0x00, 0x62): b"\x1b[15;5~",  # Ctrl+F5
    (0x00, 0x63): b"\x1b[17;5~",  # Ctrl+F6
    (0x00, 0x64): b"\x1b[18;5~",  # Ctrl+F7
    (0x00, 0x65): b"\x1b[19;5~",  # Ctrl+F8
    (0x00, 0x66): b"\x1b[20;5~",  # Ctrl+F9
    (0x00, 0x67): b"\x1b[21;5~",  # Ctrl+F10
    (0xE0, 0x89): b"\x1b[23;5~",  # Ctrl+F11
    (0xE0, 0x8A): b"\x1b[24;5~",  # Ctrl+F12
    # Alt + Function keys
    (0x00, 0x68): b"\x1b[1;3P",  # Alt+F1
    (0x00, 0x69): b"\x1b[1;3Q",  # Alt+F2
    (0x00, 0x6A): b"\x1b[1;3R",  # Alt+F3
    (0x00, 0x6B): b"\x1b[1;3S",  # Alt+F4
    (0x00, 0x6C): b"\x1b[15;3~",  # Alt+F5
    (0x00, 0x6D): b"\x1b[17;3~",  # Alt+F6
    (0x00, 0x6E): b"\x1b[18;3~",  # Alt+F7
    (0x00, 0x6F): b"\x1b[19;3~",  # Alt+F8
    (0x00, 0x70): b"\x1b[20;3~",  # Alt+F9
    (0x00, 0x71): b"\x1b[21;3~",  # Alt+F10
    (0xE0, 0x8B): b"\x1b[23;3~",  # Alt+F11
    (0xE0, 0x8C): b"\x1b[24;3~",  # Alt+F12
}

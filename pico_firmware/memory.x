MEMORY {
    /* The second-stage bootloader (BOOT2) */
    BOOT2 : ORIGIN = 0x10000000, LENGTH = 0x100

    /* The rest of the external flash for application code */
    /* Pico W has a 2MB external flash */
    FLASH : ORIGIN = 0x10000100, LENGTH = 2048K - 0x100

    /* The on-chip SRAM */
    RAM   : ORIGIN = 0x20000000, LENGTH = 256K
}

SECTIONS {
    /* Insert the Boot2 stage at the very beginning of the flash image */
    .boot2 ORIGIN(BOOT2) :
    {
        KEEP(*(.boot2));
    } > BOOT2
} INSERT BEFORE .text;
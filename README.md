![# OctoPrint-MeatPack](https://raw.githubusercontent.com/scottmudge/OctoPrint-MeatPack/master/MeatPack_Logo.png)

Getting to the **meat** of g-code. Easy, fast, effective, and automatic g-code compression!

## Current Features (v1.4.1)

1. Fully working g-code compression ("MeatPack") support for compatible Prusa printers. *NOTE:* please find builds of the official Prusa Firmware with compression support here: https://github.com/scottmudge/Prusa-Firmware-MeatPack
2. Added extra data to the "State" side-bar content, updated in real time. It shows transmission statistics:
![image](https://user-images.githubusercontent.com/19617165/103969227-79963080-5133-11eb-95f1-a39866031f21.png)

    * "**Packed Tx**" - This is the *actual* amount of data sent over the serial connection. The data that has been packed.
    * "**Total Tx**" - This is the *effective* amount of data sent over the serial connection, after it is unpacked on the other end. Should be close to the original (though OctoPrint often adds error checking data to lines of g-code, so it will be a bit higher).
    * "**Comp. Ratio**" - This is the *compression ratio*, bascially a measure of how much bandwidth you are gaining/saving. It's the factor by which the data has been effectively shrunk.
    * "**TX Rate**" - This is a measure of how much data is being sent over the serial connection per second (average). Updated every ~2 seconds.
    * "**Packing State**"-- Lets you know if MeatPack compression is enabled or not.


    __NOTE__: This extra text section can be disabled in the plugin options page.

3. A feature called "Whitespace Removal", which strips away all unnecessary whitespace from outgoing gcode on the serial port. This also allows the 'E' character to be packed in place of the ' ' space character. This effectively boosts the compression ratio down to 0.55!
4. Added an optional feature (can be enabled in plugin settings) to play a "meatball" song on the printer after a print is completed.  See the bottom of the readme why everything is "meat" themed.

## NOTE: To use MeatPack, please install a compatible version of the Prusa firmware here:

https://github.com/scottmudge/Prusa-Firmware-MeatPack

MeatPack-support (MP-Firmware v1.1.0) Firmware Release v3.9.3: https://github.com/scottmudge/Prusa-Firmware-MeatPack/releases/tag/v3.9.3-MP1.1.0

### Only version 3.9.3 from the fork above is compatible!

## Installation

**NOTE:** The plugin has been submitted to the official OctoPrint plugins repository, but is pending review and approval. To manually install, please follow the directions below.

1. Open a terminal or console (or SSH into your Raspberry Pi if using one) and activate OctoPrint's virtual environment (Python). Typically this will be in `~/oprint/`. You can activate the virtual environment by using the following command: 

`source ~/oprint/bin/activate`

2. After activating the OctoPrint environment, run the following command:

`pip install https://github.com/scottmudge/OctoPrint-MeatPack/archive/v1.2.11.zip`

3. Restart your OctoPrint server, or restart the machine.

4. After installation, you should see a "MeatPrint" options page, and a new "TX Statistics" section in the "State" side bar section (if connected to your printer).

### Known Limitations:

1. This requires a minor modification to your printer's firmware! I have currently only compiled modified firmware for Prusa's MK3/3S printers! 

I would like to integrate these changes into Marlin or similar firmwares as well. The changes are very minor, and only require placing a couple function calls at the location where serial characters are read and parsed. In Prusa's firmware, this is in `cmdqueue.c`. 

Feel free to use the `MeatPack.h` and `MeatPack.cpp` files in the firmware repository and use them in other firmwares (perhaps use it as a git module, to keep it up to date if I make modifications). If you use it, just make sure you attribute me (and keep the name... it's fun!). You can see how I integrated it with the serial connection in `cmdqueue.c`. It's fairly simple.

2. It doesn't work with the Virtual Printer in OctoPrint. Obviously... it's not a real serial connection.

## Why compress/pack G-Code? What is this?

It's been often reported that using OctoPrint's serial interface can often cause performance bottlenecks for printer 
firmware. Many popular printers (e.g., Prusa's MK3) are limited to ~115200 baud. For many simple prints, this 
works fine. But for prints with numerous, small, or quickly-traversed curves, this can pose a problem.

In g-code, these many small curves are broken down into very short line-segments. These line segments are each 
described as cartesian points, for instance:

```
...
G1 X125.824 Y95.261 E0.00907
G1 X125.496 Y95.249 E0.01145
G1 X123.181 Y92.934 E0.11420
...
```

All this text might describe only a couple hundred microns of travel. When printing at higher speeds, you can see how 
much text actually needs to be transferred over the serial connection.

This can cause stuttering or other issues while printing, leading to sub-par print quality.

There have been a few attempts to get around this problem in the past. One example, 
[Arc Welder](https://plugins.octoprint.org/plugins/arc_welder/), replaces these linear line segments with
close-approximate arc equivalents (radians + radius). This does solve the problem of reducing g-code size,
but not all printer firmwares are compatible with these arc-type g-codes, and it is left up to the printer
firmware to linearize these arcs back into cartesian line segments. Not all firmwares do this well, and often
the firmware CPU can be bogged down with this costly computation.

## So what does MeatPack do?

MeatPack takes a different approach. Instead of modifying the g-code or replacing commands, it insteads uses 
a more efficient way of transferring the data from PC/Host to Firmware.

G-code at its core is a fairly simple language, which uses a restricted alphabet. There are only a few characters which
are actually being used to represent a vast majority of g-code -- numbers, decimal point, a few letters ('G', 'M', 'E',
etc.), and other utilitiy characters (newline, space, etc.).

I performed a basic histographic analysis of about a dozen g-code files, and found that **~93%** of all g-code
uses the same **15 characters**! And yet we are using characters sized to fit a potential 256-character alphabet! 

So what **MeatPack** does is get to the **meat** of the g-code! At its core, **MeatPack** is dynamically packing 2
characters into a single 8-bits/1-byte, effectively doubling data density. Using a lookup table, **MeatPack** is able to
represent any character from the list of the 15-most-common found in g-code with only 4-bits.

Why only 15-most common if 4-bits allows 16 possible characters? Well I also needed a way to send full-width characters 
in the event that any character *does not* fall into the list of the 15-most common. So the 16th permutation 
(`0b1111`) is used as a flag to tell the unpacker that it should expect a full-width character at some point.

**MeatPack** also provides for a rudimentary communication/control layer by using a special character (0xFF) sent in a 
specific sequence. 0XFF is virtually never found naturally in g-code, so it is can be considered a reserved character.

## How does it work?

Here is an example. Take the following "G1" command.

`G1 X113.214 Y91.45 E1.3154`

It is effectively packed as the following -- note that parenthetical groups (XX) indicate that the contents are packed as a single byte:

`(G1) ( X) (11) (3.) (21) (4 ) (9#)* (Y) (1.) (45) (# )* (E) (1.) (31) (54) (\n)`

or with "Whitespace Removal" active:

`(G1) (X1) (13) (.2) (14) (#9) (Y) (1.) (45) (E1) (.3) (15) (4\n)`

\* these bytes don't show character order, but bit order. Higher order bits on left, lower order bits on right. See below. The other characters are sequential and only show how they are paired in bytes. 

The packer reorders some characters if the full width character is surrounded by packable characters. The # here is a flag (0b1111) which tells the unpacker where the following full width character should go.

In this way, 4 bits aren't wasted telling the packer that only one full width character is coming up. 0xFF (0b11111111) tells the unpacker that the next 2 bytea are full width.

If 0b1111 is in the lower 4 bits, the full width character is immediately following, and the packed character in the upper 4 bits goes after the full width character. If it's in the higher 4 bits, the full width character goes after the character packed in the lower 4 bits. And if both upper and lower 4 bits are set to 1111, the next 2 characters are full width.

So 16 bytes in this example (13 bytes with Whitespace Removal active). This is on-par or better than binary packing.

This minor reordering is undone in the unpacking stage in the firmware. A little more complex, but it allows slightly more data to be packed. 

This is also why the command sequence is 2 0xFF bytes in a row, followed by a command byte. If packing is enabled, 0xFF means the next character is some standard ASCII character (or at the very least not 0xFF), so 2 0xFF bytes in a row would never occur naturally except in these control/command sequences. And if packing is disabled, 0xFF is an invalid g-code character (the Prusa firmware even discards all bytes higher than 127U). This command signal preamble can be increased to 3 or more 0xFF bytes if some firmwares tend to have these bytes in error more frequently. But from what I've seen, it's generally 0x0 or null bytes which are received or sent in error.  For instance, in noisy or unshielded connections. 

## Why "Meat"? 

My cat's name is Meatball, I thought it sounded fun. 

Obligatory cat photo:

![photo](https://i.imgur.com/QgUuyzs.png)

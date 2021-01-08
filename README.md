# OctoPrint-MeatPack
Getting to the **meat** of g-code. A real-time, CPU-easy, gcode compression/packing algorithm developed by Scott Mudge

## Current Features


1. Fully working g-code compression ("MeatPack") support for compatible Prusa printers. Please find builds of the official Prusa Firmware with compression support here: https://github.com/scottmudge/Prusa-Firmware-MeatPack
2. Added extra data to the "State" side-bar content, updated in real time. It shows transmission statistics:
![image](https://user-images.githubusercontent.com/19617165/103969227-79963080-5133-11eb-95f1-a39866031f21.png)
This can be disabled in the plugin options page.
3. Added an optional feature (can be disabled in plugin settings) to play a "Mario coin" noise on the printer after a print is completed.

## NOTE: To use MeatPack, please install a compatible version of the Prusa firmware here:

https://github.com/scottmudge/Prusa-Firmware-MeatPack

MeatPack-support Firmware Release 3.9.3: https://github.com/scottmudge/Prusa-Firmware-MeatPack/releases/tag/3.9.3-MeatPack

### Only version 3.9.3 from the fork above is compatible! P

## Installation

1. Open a terminal or console (or SSH into your Raspberry Pi if using one) and activate OctoPrint's virtual environment (Python). Typically this will be in `~/oprint/`. You can activate the virtual environment by using the following command: 

`source ~/oprint/bin/activate`

2. After activating the OctoPrint environment, run the following command:

`pip install git+https://github.com/scottmudge/OctoPrint-MeatPack.git`

3. Restart your OctoPrint server, or restart the machine.

4. After installation, you should see a "MeatPrint" options page, and a new "TX Statistics" section in the "State" side bar section (if connected to your printer).

### Known Issues:

1. This doesn't work with any firmware __except the firmware I modified above with added MeatPack support!__. 

Feel free to copy the `MeatPack.h` and `MeatPack.cpp` files in the firmware repository and use them in other firmwares. It's very portable code, with only the serial output needing to be ported/modified. If you use it, just make sure you attribute the forks of other firmware to me (and keep the name... it's fun!). You can see how I integrated it with the serial connection in `cmdqueue.c`. It's fairly simple.

2. It doesn't work with the Virtual Printer in OctoPrint.

## How does it work?

This plugin creates a wrapper around the serial.Seral() object. This wrapper overrides the read and write operations to provide extra utility. The PackingSerial class manages all of the state control and data packing/compression automatically. State control is managed by sending specific data packets to the modified firmware, telling it to turn on or turn off MeatPacking support dynamically. Once enabled, the PackingSerial verifies that it is enabled in the firmware by sending a query command, and once the states are synchronized, it sends data with the packing approach detailed below.

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

## Why "Meat"? 

My cat's name is Meatball, I thought it sounded fun. 

Obligatory cat photo:

![photo](https://i.imgur.com/QgUuyzs.png)


"""Remote Cambadge for Hackaday Superconference 2017

This runs under MicroPython in an 8266-based board like an
Adafruit 8266 Huzzah, connected to the serial port on the
expansion header of the Cambadge from the 2017 Hackaday
Superconference.

https://www.adafruit.com/product/2471
https://hackaday.io/project/27427-camera-badge-for-supercon-2017

The bare Cambadge has a camera and a screen, and lets the user
record still photos in BMP format and videos in AVI format.
The purpose of the Remote Cambadge is to make these images
available remotely via WiFi.
"""

import machine
import network
import os
import socket
import uio
import ure


hex_id = ''.join('{:02x}'.format(b) for b in machine.unique_id())

html = """<!DOCTYPE html>
<html>
    <head> <title>Badge %s</title> </head>
    <body> <h1>Remote Camera Badge Adapter</h1>
    <p>Brought to you by @MustBeArt, @Abraxas3D, et al.</p>
    <h2>Files on Badge %s</h2>
        <table border="0">
        <tr><th>File</th><th align="right">Bytes</th></tr>
        %%s
        </table>
    </body>
</html>
""" % (hex_id, hex_id)

web_root = '/WWW'
web_port = 80
web_essid = 'Cambadge-' + hex_id
web_channel = 1


def dir_walk():
    """Walk the directory tree of web files

    Scans only one level of subdirectories.

    Returns: a list of relative paths to the files.
    """
    files = []
    dn_list = []
    # Scan the root directory. Output file names, remember directories.
    for (fn, ftype, _) in os.ilistdir(web_root):
        if ftype == 0x4000:
            dn_list.append(fn)
        elif ftype == 0x8000:
            files.append(fn)

    # Scan each top-level subdirectory and output paths.
    for dn in dn_list:
        for fn in os.listdir(web_root+'/'+dn):
            files.append('%s/%s' % (dn, fn))

    return files


# Create our own WiFi network with a unique recognizable name
ap = network.WLAN(network.AP_IF)
ap.config(essid=web_essid, channel=web_channel)
ap.active(True)

addr = socket.getaddrinfo('0.0.0.0', web_port)[0][-1]
s = socket.socket()
s.bind(addr)
s.listen(1)

print('Web server listening on port', web_port)

while True:
    cl, addr = s.accept()
    cl.setblocking(True)
    print('client connected from', addr)
    respond_in_badge_format = False
    cl_file = cl.makefile('rwb', 0)
    while True:
        line = cl_file.readline()
        if not line or line == b'\r\n':
            break

        # Scan the header for a GET command
        match = ure.match('GET (.+) ', line)
        if match:
            query = match.group(1).decode('ascii')
            if query == '/BadgeLife':
                respond_in_badge_format = True
                print("Responding to a badge query!")
            else:
                try:
                    if os.stat(web_root+'/'+query):
                        print('Responding with a file!')
                except OSError:
                    query = None
                    print('No match, give the default response.')

    if respond_in_badge_format:
        # Header with interface version number and badge ID in hex
        response = 'Badge 0.1 %s\r\n' % hex_id

        # A line with each filename
        for fn in dir_walk():
            response += '%s\r\n' % fn

        # Terminate list with a slash
        response += '/\r\n'

    elif query:
        try:
            response = open(web_root+'/'+query, 'rb').read()
        except Exception:
            response = "Error reading file!\r\n"

    else:   # Send the default response
        rows = ['<tr><td><a href="/%s">%s</a></td>'
                '<td align="right">%d</td></tr>'
                % (fn, fn, os.stat(web_root+'/'+fn)[6]) for fn in dir_walk()]
        response = html % '\n'.join(rows)

    cl.sendall(response)       # blocks until it sends all of the response
    cl.close()

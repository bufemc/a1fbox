# Airport1 Fritzbox Tools

Fritz!Box tool set by [Airport1], e.g. parse the call monitor, phonebook handling, automated call blocking.

### Ingredients
- CallMonitor: connect and listen to call monitor on port 1012 of the Fritzbox
    - CallMonitorLine: line parser and phone number anonymizer
    - CallMonitorLog: optional logger for lines, either one big file or daily files

- CallBlocker: _EXPERIMENTAL_ (WIP, "API" is not final) - listen to call monitor and check RING events 
    - CallerInfo: Rate and examine a phone number (e.g. do scoring or reverse search)
    - CallBlockerLog: optional logger for actions, either one big file or daily files
    
- Phonebook: inherited and extended from [fritzconnection]'s FritzPhonebook
    - Retrieve all contacts from a phonebook, see [fc-issue-53], [fc-issue-55] 
    - Add contact to phonebook, see [fc-issue-50]    
    
### Setup

Use ```pip install -r requirements.txt``` to install dependencies. 
Adjust ```config.py``` to your Fritz!Box settings (hint: you can also set ```"fritz.box"``` 
instead of an IP). 
For an example implementation you could try to run ``` python example.py ```.

### Requirements
- Python >= 3.6 - as e.g. f'Hello, {name}!' is used
- requests, [fritzconnection] by Klaus Bremer aka kbr - for retrieving and manipulating phonebooks 
- Fritz!Box with
    - enabled call monitor - to enable dial ```#96*5*``` - and to disable dial ```#96*4```
    - either standard or dedicated user with password (set in ```config.py```) and enough permissions
    - an additional phonebook for cold calls, configured to block incoming numbers

### License
MIT


### Backstage

#### Issues
- CallMonitor
    - socket might stop sending data after a while, should work now by using TCP keep alive, see below
    - socket shutdown by stopping might lead to BrokenPipe exception in listener
- CallBlocker
    - still very basic, missing: handling for failing requests, area_code determination, logging
- Missing unit tests and a better package structure

#### Alternatives
If you search an alternative in PHP for automated call blocking, check out [fbcallrouter]. 
This project by Volker Pueschel aka blacksenator gave me some impulses.  

#### Data folder: ONB

Like previous mentioned project, this uses _ONB_ = OrtsNetzBereiche (Vorwahlbereiche/Vorwahlen) aka local area codes. 
The list used is from the "BNetzA" (German "Bundesnetzagentur") and should be valid for a limited period of time. 
If you want to update them, then download the offered CSV file (see link titled "Vorwahlverzeichnis")
from [BNetzA-ONB]. Unpack the archive (there can be an archive in the archive, unpack also this) 
and save the file, but renamed to ```onb.csv```, in the ./data directory.

ONB file provided here, was originally named: NVONB.INTERNET.20200610.ONB 
    
#### Guessed parameters for call monitor types (there is no official document?)
If anyone knows an official document please tell me!
- date time;RING;connection_id;caller_number;callee_number;SIP1;\n
- date time;CONNECT;connection_id;extension_id;caller_number;\n
- date time;DISCONNECT;connection_id;duration_seconds;\n
- date time;CALL;connection_id;extension_id;caller_number;callee_number;SIP1;\n

#### Raw call monitor line examples, received from a Fritzbox
These are real received lines, except for the 'xxx', the comments, and 3rd or 4th line was faked.
I provide those as there is nearly no documentation or examples. Again:
if anyone knows an official document please tell me!
``` 
16.06.20 12:25:42;RING;0;01755290xxx;732xxx;SIP1;  # Mobile calls land line
16.06.20 12:25:46;DISCONNECT;0;0;  # After rejected or after CONNECT, last number duration?
16.06.20 15:04:02;CALL;1;13;732xxx;01755290xxx;SIP1;  # Land line calls mobile
16.06.20 15:04:02;CONNECT;0;0;01755290xxx;  # Accepting a RING by caller from mobile

16.06.20 17:55:06;RING;2;07191732xxx;69xxx;SIP0;  # In-house-call from caller 732 to callee 69
16.06.20 17:55:09;CONNECT;2;10;07191732xxx;  # Call is accepted for caller (conn_id 2)
16.06.20 17:55:09;CONNECT;1;13;69xxx;  # Call is accepted for callee (conn_id 1)
16.06.20 17:55:15;DISCONNECT;2;6;  # Caller hangs up (conn_id 2), 6 seconds duration?
16.06.20 17:55:16;DISCONNECT;1;6;  # Callee is disconnected (conn_id 1), 6 seconds duration?

16.06.20 18:11:57;CALL;1;13;732xxx;01755290xxx;SIP1;  # Land line calls mobile

17.06.20 10:28:29;RING;0;07191952xxx;69xxx;SIP0; # Call from D 952 to 69
17.06.20 10:28:43;CONNECT;0;11;07191952xxx; # Connect from D accepted, 11 (extension id 11, not seconds?)
17.06.20 10:30:31;DISCONNECT;0;109; # Disconnect after accepting and talking 109 seconds?
17.06.20 10:30:57;CALL;1;11;69xxx;952xxx;SIP0; # Re-call to D, again 11 (extension id?)
17.06.20 10:31:00;DISCONNECT;1;0;
17.06.20 10:31:08;CALL;1;11;69xxx;952xxx;SIP0; # Trying several times..
17.06.20 10:31:13;DISCONNECT;1;0;
17.06.20 10:31:24;CALL;1;11;69xxx;952xxx;SIP0;
17.06.20 10:31:27;DISCONNECT;1;0;
17.06.20 10:31:54;CALL;1;11;69xxx;952xxx;SIP0;
17.06.20 10:31:58;DISCONNECT;1;0;
17.06.20 10:32:16;CALL;1;11;69xxx;952xxx;SIP0;
17.06.20 10:32:23;CONNECT;1;11;952xxx; # D accepts call
17.06.20 10:37:34;DISCONNECT;1;312; # Disconnect after 312 seconds of talking
```

#### Fritzbox's call monitor socket at port 1012 and TCP keep-alive
As written in the article [TCP-Keep-Alive-in-Wikipedia]: 
_"Transmission Control Protocol (TCP) keepalives are an optional feature, and if included must default to off."_
So, why is this important here? Because it's off by default.

If you set up the call monitor socket just without additional configuration, 
few OS will make the socket a dead-end after about 2 hours (see deep-dive links below).

Why _dead-end_? Because no more call events are received from the socket, BUT:
the socket _seems_ to be still "up and running".

The solution is easy, at least in some other languages: e.g.:
- Java: ```socket.setKeepAlive(true);```
- PHP: ```socket_set_option($socket, SOL_SOCKET, SO_KEEPALIVE, 1);```
- Python: see [TCP-Keep-Alive-in-Python], unfortunately not that "pythonic" (or do you know better?)
 
_I tried to solve it that way, but I really need feedback from Mac and Linux users if it works for them, too!_

Links:
- [TCP-Keep-Alive-in-Wikipedia]
- [TCP-Keep-Alive-in-Python]

More links - if you want to dive deeper:
- https://stackoverflow.com/questions/5686490/detect-socket-hangup-without-sending-or-receiving
- https://stackoverflow.com/questions/1480236/does-a-tcp-socket-connection-have-a-keep-alive
- https://stackoverflow.com/questions/667640/how-to-tell-if-a-connection-is-dead-in-python
- https://stackoverflow.com/questions/35861484/how-to-know-the-if-the-socket-connection-is-closed-in-python
- https://tewarid.github.io/2013/08/16/handling-tcp-keep-alive.html

[Airport1]: https://www.airport1.de/
[TCP-Keep-Alive-in-Wikipedia]: https://en.wikipedia.org/wiki/Keepalive#TCP_keepalive
[TCP-Keep-Alive-in-Python]: https://stackoverflow.com/questions/12248132/how-to-change-tcp-keepalive-timer-using-python-script
[fritzconnection]: https://github.com/kbr/fritzconnection
[fbcallrouter]: https://github.com/blacksenator/fbcallrouter
[fc-issue-50]: https://github.com/kbr/fritzconnection/issues/50
[fc-issue-53]: https://github.com/kbr/fritzconnection/issues/53
[fc-issue-55]: https://github.com/kbr/fritzconnection/issues/55
[BNetzA-ONB]: https://www.bundesnetzagentur.de/DE/Sachgebiete/Telekommunikation/Unternehmen_Institutionen/Nummerierung/Rufnummern/ONRufnr/ON_Einteilung_ONB/ON_ONB_ONKz_ONBGrenzen_Basepage.html
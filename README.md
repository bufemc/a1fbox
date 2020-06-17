# Airport1 Fritzbox Tools

Fritz!Box tool set by [Airport1], e.g. parsing the call monitor, later also adding phone entries to phonebook etc.

### Ingredients
- Callmonitor - connect and listen to call monitor on port 1012 of the Fritzbox
    - CallMonitorLine - line parser and phone number anonymizer
    - CallMonitorLog - optional logger for lines, either one big file or daily files
    
### Setup
Unfortunately no setup procedure yet. You have to adapt your Fritz!Box host in the code (e.g. by IP), then run:
```python callmonitor.py```. Setup will be provided later, especially if more tools are added.
Please do not fork yet, a setup is really coming soon.

### Requirements
- Python >= v.3.6 - as e.g. f'Hello, {name}!' is used
- Fritz!Box - with enabled call monitor - to enable dial ```#96*5*``` - and to disable dial ```#96*4```
- Later: [fritzconnection] >= v.{to_be_determined} - for retrieving and manipulating phonebooks 

### License
Not determined yet


### Backstage

#### Issues
- CallMonitor
    - socket might stop sending data after a while, should work now by using TCP keep alive, see below
    - socket shutdown by stopping might lead to BrokenPipe exception in listener
- No setup provided, yet

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


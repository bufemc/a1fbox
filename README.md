# Airport1 Fritzbox Tools

Fritz!Box tool set by [Airport1], e.g. parsing the call monitor, later also adding phone entries to phonebook etc.

### Ingredients
- Callmonitor - connect, listen, parse and print lines

### Status
Experimental - see issues. Should not be used in production, yet. REALLY ;)

### Setup
Unfortunately no setup procedure yet. You have to adapt your Fritz!Box host in the code (e.g. by IP), then run:
```python callmonitor.py```. Setup will be provided later, especially if more tools are added.
Please do not fork yet, a setup is really coming soon.

### Requirements
- Python >= v.3.6 - as e.g. f'Hello, {name}!' is used
- Fritz!Box - with enabled call monitor - to enable dial ```#96*5*``` - and to disable dial ```#96*4```
- Later: [fritzconnection] >= v.{to_be_determined} - for retrieving and manipulating phonebooks 

#### Issues
- CallMonitor: socket stops sending data after a while, re-establishing the connection might help
- CallMonitor: socket shutdown by stopping might lead to BrokenPipe exception in listener
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
```

## License
 
Not determined yet

[fritzconnection]: https://github.com/kbr/fritzconnection
[Airport1]: https://www.airport1.de/
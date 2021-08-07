# Airport1 Fritzbox Tools

<img alt="Python versions" src="https://camo.githubusercontent.com/4b34d92404f5a39a6b41ee03b34a2926bbc70db8/68747470733a2f2f696d672e736869656c64732e696f2f707970692f707976657273696f6e732f667269747a636f6e6e656374696f6e2e737667"/> <img src="https://camo.githubusercontent.com/232174f26bac5f71ba94b19698d7374192fbe304/68747470733a2f2f696d672e736869656c64732e696f2f707970692f6c2f667269747a636f6e6e656374696f6e2e737667"/><p/>

Short name **a1fbox**. This is a Fritz!Box tool set by [Airport1]. E.g. parse the call monitor, phonebook handling, automated call blocking.
All is still in state _EXPERIMENTAL_ (work in progress, "API" is not final). Use at own risk.

### Setup

Use ```pip install -r requirements.txt``` (depending on your OS replace the start of this line
with ```pip3``` or  ```python3 -m pip```) to install dependencies. 
Adjust ```config.py``` to your Fritz!Box settings (hint: you can also set ```"fritz.box"``` 
instead of an IP). 
For an example implementation run ```python example.py``` (or, depending on your OS use ```python3 example.py``` to
explicitely use the Python version 3, and not 2).

### Requirements
- Python >= 3.6 - as e.g. f'Hello, {name}!' is used
- Packages ```requests``` and ```json5``` and [fritzconnection] by Klaus Bremer aka kbr 
- A Fritz!Box, reachable within your network with your credentials, and if using call monitor or blocker:
    - enabled call monitor - to enable dial ```#96*5*``` - and to disable dial ```#96*4```
    - either standard or dedicated user with password (set in ```config.py```) and enough permissions
    - an additional phonebook for cold calls, configured to block incoming numbers
- It is assumed you are and run this in Germany, if not, please contact me so we can adapt it to your environment

### Description
Idea was to create a call blocker for cold calls. I tried to build modules that were as independent as possible,
having same naming, even same logging scheme. So they could be used as building blocks, combined in different ways.
So you could run the call monitor alone, but also combined with the call blocker. Or you could just do rating for
phone numbers or reverse search. Or add contacts to your phonebook. Feedback is highly appreciated.

### Ingredients
- FritzConn: small helper to use only one FritzConnection for all modules 
    - ```config.py``` file defines the paramters to connect (DO NEVER COMMIT/SHARE YOUR PASSWORD!)

- CallMonitor: connect and listen to call monitor on port 1012 of the Fritzbox
    - CallMonitorLine: line parser and phone number anonymizer
    - CallMonitorLog: optional logger for lines, either one big file or daily files

- CallBlocker: listen to call monitor and check RING events 
    - CallBlockerLine: line parser and phone number/name anonymizer
    - CallBlockerLog: optional logger for actions, either one big file or daily files

- CallInfo: examine an unknown phone number for rating or naming
    - CallInfoType: e.g. Tellows for scoring or RevSearch for reverse search via dasOertliche

- CallPrefix: retrieve and handle own area code and country code, resolve name, using data:
    - ONB: (German) "Ortsnetzbereiche", area codes for Germany for landline numbers (from BNetzA)
    - RNB: (German) "Mobile Dienste, zugeteilte RNB", codes for mobile numbers (from BNetzA)
    - countryio-phone / -names: country codes and names (from country.io)

- CallList: is not a module or class yet!
    - Examples only, how to traverse and resolve last 400 calls
         
- Phonebook: inherited and extended from [fritzconnection]'s FritzPhonebook
    - Retrieve all contacts from a phonebook, but remove internal numbers, see [fc-issue-53], [fc-issue-55]
    - Find a name for a number in phonebook, even if with/without area or country code 
    - Add contact to phonebook, see [fc-issue-50], but Umlauts are still a pain    

### Autostart on a Raspberry Pi

The following is an example which works here on a Raspberry Pi 4 with Raspberry OS 32.
First retrieve the (your!) correct working directory, also check if your Python3 is 
addressed by ```python3```. Then enter ```crontab -e``` and add this (adapt it to your needs):

```
@reboot (sleep 30 && cd /home/pi/work/a1fbox && /usr/bin/env /usr/bin/python3 /home/pi/work/a1fbox/example2.py >> /home/pi/work/fb.log) &
```

Then do a reboot. Check e.g. with ```ps -elf | grep python``` whether it works.

Explanation: the sleeping time seems to be mandatory, otherwise the script might fail to start
(e.g. no network available at first). But the full pipe is sent to background, so it should not delay
the booting process. The changing into the working directory is (currently) required, so it will
create the log on the correct position. Optionally you could log the output as seen into fb.log.

### License
MIT


### Backstage

#### Alternatives
If you search an alternative in PHP for automated call blocking, check out [fbcallrouter]. 
This project by Volker Pueschel aka blacksenator gave me some impulses.  

#### Data folder: ONB, RNB, CountryIO

Like previous mentioned project, this uses _ONB_ = OrtsNetzBereiche (Vorwahlbereiche/Vorwahlen) aka local area codes. 
The list used is from the "BNetzA" (German "Bundesnetzagentur") and should be valid for a limited period of time. 
If you want to update them, then download the offered CSV file (see link titled "Vorwahlverzeichnis")
from [BNetzA-ONB]. Unpack the archive (there can be an archive in the archive, unpack also this) 
and save the file, but renamed to ```onb.csv```, in the ./data directory.

RNB are "Mobile Dienste, zugeteilte RNB, Stand: 07.07.2021". Data was copied from https://bit.ly/3jyZBU8 now -
just replace the first space or tab with a semicolon. 

Country data is taken from http://country.io/data/ - http://country.io/phone.json and http://country.io/names.json -
downloaded 28th June 2020, but not sure how accurate the data is.

Further numbers used in Germany:
https://www.bundesnetzagentur.de/DE/Sachgebiete/Telekommunikation/Unternehmen_Institutionen/Nummerierung/Rufnummern/Rufnummern_node.html

ONB file provided here, was originally named: NVONB.INTERNET.20210728.ONB (no change to 2020)

Further sources are noted in internal code!
    
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

#### Planning and issues

ToDo and/or further planning (pb = phonebook):
- Add GN section of https://www.itu.int/oth/T0202.aspx?parent=T0202 to data and parse it in callprefix?
- Numbers in phonebooks cannot only have local area prefix (or country?) code, but also spaces like "<prefix> <number>",
    when retrieving remove spaces (and maybe if same country code)
- Architecture pains: should fritzconn be passed if required, and abstraction layers be used?
- When caller uses CLIR there is no number, what should happen, e.g. extra state CLIR, should be blocked (is it possible?) or not
- When caller uses country code from abroad, should be blocked or not (blocking action should go in extra method)
- Unit tests
- Config and initialization is a mess ATM, since moved to pseudo-package (setup still missing)
- Config should be read only once/kept only once, currently read from several modules in package, solution maybe like fritzconnection/core in __init__.py?
- CallBlockerLog sometimes doubled entries?
- CallPrefix needs refactoring 
    - should an area code or country code be an instance of CallPrefix, and the helper class get another name, like CallPrefixManager?
    - should the very own Fritzbox area code and country code also be stored as CallPrefix or go into specialised CallPrefixFritzbox(CallPrefix), or is just an extra method in CallPrefixManager?
- CallInfo could do a combined search: first tellows scoring, then rev search, use tellows result but with name of rev search, if name is longer?
- CallInfo should be smarter:
    - Reverse search (/Tellows) only if number not starting with 00 or is 0049?
    - Numbers like 00114989998288xx need to parse also?:         
        - https://www.wemgehoert.de/nummer/00114989998288xxx
        - https://telefonnummer.net/rufnummer/114989998288xxx
- CallInfo and CallPrefix can maybe merged into one?        
- Injection of numbers to or instead of call monitor (mockup?) for: whitelist, blacklist, block, pass
- Check possibility to merge/generalize CallBlockerInfo and CallBlockerLine - e.g. by inheritance classA(classB)
- Method to retrieve last (400 max?) phone numbers and examine/rate them (BUT, by using a cache!) (except if in pbs?)
- Log (blocked only?) calls to telegram channel via a bot?
- Add update (+ delete?) contact method e.g. to improve entries to provide better names
- Replace phonebook contacts with missing local area code with full numbers
- Documentation: how to set up for a Raspberry Pi, e.g. as a service, how to set up a bot for telegram channel..
- Old notes:
    - CallMonitor
        - socket might stop sending data after a while, should work now by using TCP keep alive, see below
        - socket shutdown by stopping might lead to BrokenPipe exception in listener
    - CallBlocker
        - still very basic, missing: handling for failing requests, area_code determination, logging
    - Missing unit tests and a better package structure
- "Lass mich dir einen kostenlosen Ratschlag geben. Bring die Nummer erst ins internationale Format. Dann guck als erstes nach der Ländervorwahl und dann die nationale nummer abarbeiten. Um Regex wirst du wohl nicht drum rum kommen."


[Airport1]: https://www.airport1.de/
[TCP-Keep-Alive-in-Wikipedia]: https://en.wikipedia.org/wiki/Keepalive#TCP_keepalive
[TCP-Keep-Alive-in-Python]: https://stackoverflow.com/questions/12248132/how-to-change-tcp-keepalive-timer-using-python-script
[fritzconnection]: https://github.com/kbr/fritzconnection
[fbcallrouter]: https://github.com/blacksenator/fbcallrouter
[fc-issue-50]: https://github.com/kbr/fritzconnection/issues/50
[fc-issue-53]: https://github.com/kbr/fritzconnection/issues/53
[fc-issue-55]: https://github.com/kbr/fritzconnection/issues/55
[BNetzA-ONB]: https://www.bundesnetzagentur.de/DE/Sachgebiete/Telekommunikation/Unternehmen_Institutionen/Nummerierung/ONRufnr/ON_Einteilung_ONB/ON_ONB_ONKz_ONBGrenzen_node.html

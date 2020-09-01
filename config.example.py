# Copy this to config.py in the same folder, and  adapt (the copy!) to your credentials!

# Config like in the documentation for fritzconnection, which is also used in this project
FRITZ_IP_ADDRESS = 'fritz.box'
FRITZ_TCP_PORT = 49000
FRITZ_TLS_PORT = 49443
FRITZ_USERNAME = 'dslf-config'
FRITZ_PASSWORD = ''

# Inform via telegram URL: add your bot to group or channel, then forward or invite @getidsbot or @RawDataBot
# to get your chat_id.. Then set here: botNumber:token and chat_id. Leave blank if TG bot should not be used.
TELEGRAM_BOT_URL = ''
# TELEGRAM_BOT_URL = "https://api.telegram.org/botNUMBER:TOKEN/sendMessage?chat_id=CHAT_ID&text="

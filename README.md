# OSC-based JoyCon (Haptics) for ChilloutVR/VRChat

Link Nintendo Switch Joy-Cons to [Chillout VR](https://store.steampowered.com/app/661130/ChilloutVR/)/VRChat! Uses [OSC Mod](https://github.com/kafeijao/Kafe_CVR_Mods/tree/master/OSC) in ChilloutVR and the [OSC system](https://docs.vrchat.com/docs/osc-overview) in VRChat.

For now, only simple on/off rumble haptics are supported!

# Requirements

 - Nintendo Switch Joy-Con controller(s). **Only tested with knockoffs from Aliexpress.**
 - A customisable avatar or a compatible avatar
 - Bluetooth Dongle or similar. [You can use another Windows device as relay](#relay)
 - Something to attach controller to body/headset straps, for example ["Exercise Patch Self Adhesive Tape Sports Gym Fitness"](https://www.google.com/search?q=Exercise+Patch+Self+Adhesive+Tape+Sports+Gym+Fitness)
 - Unity editor
 - `vrcjoycon.exe` from this repository's [Releases](https://github.com/Python1320/vrcjoycon/releases/tag/vrcjoycon)
 - **ChilloutVR**
   - [OSC Mod](https://github.com/kafeijao/Kafe_CVR_Mods/tree/master/OSC) (Recommended to install via [CVR Assistant](https://github.com/knah/CVRMelonAssistant))
   - Other avatars need [CVR Pointer]( https://documentation.abinteractive.net/cck/components/pointer/?h=pointer#cvr-pointer) on at least one index finger.
   - Your avatar needs [CVR Advanced Avatar Trigger](https://documentation.abinteractive.net/cck/components/aas-trigger/) boxes and parameters

# HELP WANTED
Only tested with knockoff joycons. Does it work with real joycons? Apparently not. We need to fix this!

# Linux


### **1. Installation**

Only tested on Debian 12 (bookworm) and python 3.11

Steps
```bash

# Our dependencies
sudo apt install libhidapi-dev

# https://innovativeinnovation.github.io/ubuntu-setup/python/pyenv.html
# Pyenv dependencies
sudo apt install make build-essential libssl-dev zlib1g-dev libbz2-dev \
libreadline-dev libsqlite3-dev wget curl llvm libncursesw5-dev \
xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev

# Get pyenv so we can get python 3.11 exactly
curl https://pyenv.run | bash

# ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# ^^^ Follow comments above to install pyenv lines in .bashrc ^^^
# ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

pyenv install 3.11 # build 3.11 python
pyenv virtualenv 3.11 joycon # create joycon virtualenv

. .bashrc # reload .bashrc (or restart shell here)

git clone "https://github.com/Python1320/vrcjoycon.git" && \
cd vrcjoycon && \
pyenv local joycon

# Make sure you see (joycon) prefix on your shell now

 # install poetry dependency manager
pip install poetry # OR: curl -sSL https://install.python-poetry.org | python3

poetry install # install python dependencies with poetry

####### Do steps 2 and 3 below and (*) ##########

cd src
./main.py

# Start controllers for discovery

# Modify config

${EDITOR:-nano} config.ini


```
(*) you may need to try `poetry add hid` and `poetry add hidapi` to find a working one (remove the other one).

### **2. hid_nintendo kernel module must not be loaded**
```bash
echo "blacklist hid_nintendo" > /etc/modprobe.d/blacklist_hid_nintendo.conf
rmmod hid_nintendo
```

### **3. Install udev rules**

See: https://www.reddit.com/r/Stadia/comments/egcvpq/comment/fc5s7qm/

```bash
cat << 'EOF' > /etc/udev/rules.d/50-nintendo-switch.rules
# Switch Joy-con (L) (Bluetooth only)
KERNEL=="hidraw*", SUBSYSTEM=="hidraw", KERNELS=="0005:057E:2006.*", MODE="0666"

# Switch Joy-con (R) (Bluetooth only)
KERNEL=="hidraw*", SUBSYSTEM=="hidraw", KERNELS=="0005:057E:2007.*", MODE="0666"

# Switch Pro controller (USB and Bluetooth)
KERNEL=="hidraw*", SUBSYSTEM=="hidraw", ATTRS{idVendor}=="057e", ATTRS{idProduct}=="2009", MODE="0666"
KERNEL=="hidraw*", SUBSYSTEM=="hidraw", KERNELS=="0005:057E:2009.*", MODE="0666"

EOF

```

Run `udevadm control --reload-rules`

# TODO
 - Example haptics avatar + world (please submit in PR!)
 - Button input possibility
 - Gyroscope?
 - Switch joy-con to poll only to reduce wireless interference (partially done)

# Haptics: Setting Up / Usage
### **Unity** (For Chillout VR)

Rather simple. Just add a few components with right parameter name and it should just work.

  1. Add joyconrumble1 to avatar parameters
     
     ![Add joyconrumble1 to avatar parameters](https://user-images.githubusercontent.com/207340/188220202-71f9448d-4c50-4405-a0eb-7d022e5a590a.png)
  2. Add [CVR Advanced Avatar Trigger](https://documentation.abinteractive.net/cck/components/aas-trigger/) to your head
     
     ![Add CVR Advanced Avatar Trigger](https://user-images.githubusercontent.com/207340/188219981-bdeecdf4-a738-4fd1-9dfd-59fb5beacae5.png)
  3. Add [CVR Pointer]( https://documentation.abinteractive.net/cck/components/pointer/?h=pointer#cvr-pointer) on at least one finger
     
     ![Add CVR Pointer](https://user-images.githubusercontent.com/207340/188220053-e38ae570-91c1-41c0-a9de-9ac943f99a3f.png)

### **Unity** (for VRCHat)
  1. Position one or multiple [Contact Receivers](https://docs.vrchat.com/docs/contacts#vrccontactreceiver) components to your chosen avatar bone
     1. Choose at least some collision tags or you will receive no contacts 
     2. Haptics can be set to `local only`. `Allow Self` is recommended for testing.
     3. Select `Proximity` from `Receiver Type`.
     4. Set target parameter to `joyconrumble1`. For right controller choose `joyconrumble2`. 

        ![componentdetails](images/help2.png)
     5. Add the above parameters to your [animator parameters](https://docs.vrchat.com/docs/animator-parameters) with default float value of 0.0. This is used by OSC to relay the status to VRCJoyCon.
        
        ![animator](images/help1.png)

### **VRChat**
  1. Put controllers into pairing mode by pressing the pairing button.
  2. Pair controllers manually over Bluetooth with Windows.
  3. Launch [vrcjoycon.exe](https://github.com/Python1320/vrcjoycon/releases/tag/vrcjoycon)
  4. When pairing is successful, the controller should vibrate. You may need to press the pair button in the controllers a few times before Windows notices the controllers. They should say "connected" in the windows settings when this is so.
  5. In case of trouble, test with other joycon software first
  6. Launch **VRChat** if not already launched
     1. From the VRChat's **circular menu**, inside **settings**, inside **OSC**, choose **Enable** OSC. Additional help [here](https://docs.vrchat.com/docs/osc-overview#enabling-it).
      (*If the haptics do not work, try reset configuration option in the same menu* **ATTN.** The OSC Debug menu does not help you with debugging haptics, only output)

# Relay
If you have no bluetooth on your VR PC or are experiencing interference it should also be possible to use `vrcjoycon.exe` on a different Windows Laptop, for example.

 1. You will need to configure VRChat to relay the OSC output data to your target computer: https://docs.vrchat.com/docs/osc-overview#vrchat-ports
 2. Start `vrcjoycon` with command line arguments `vrcjoycon.exe --listen=any --port=9001`
       - You can replace `any` with an IP address. Any is an alias for `0.0.0.0`
       - The default port is 9001
       - Make sure your firewall allows listening on `UDP` protocol port `9001` for `vrcjoycon.exe`

# Troubleshooting

Test with OSC receiver to see if your avatar is transmitting. Try transmitting `1` to `/avatar/parameters/joyconrumble1` with OSC sender to see if `vrcjoycon.exe` works.


# Credits / components used
 - [joycon-python](https://github.com/tocoteron/joycon-python) library

# License

PENDING MISSING LICENSE ON: https://github.com/tocoteron/joycon-python


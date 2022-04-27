# VRCJoyCon

Link Nintendo Switch Joy-Cons to VRChat! Uses the new [OSC system](https://docs.vrchat.com/docs/osc-overview). 

For now, only simple on/off rumble haptics are supported!

# Requirements

 - Nintendo Switch Joy-Con controller(s). **Only tested with knockoffs from Aliexpress.**
 - A customisable avatar or a compatible avatar 
 - Unity editor
 - `vrcjoycon.exe` from this repository's Releases

# TODO
 - Example haptics avatar
 - Debug help
 - Button input

# Haptics: Setting Up / Usage

**Unity**
  1. Position one or multiple [Contact Receivers](https://docs.vrchat.com/docs/contacts#vrccontactreceiver) components to your chosen avatar bone
     1. Choose at least some collision tags or you will receive no contacts 
     2. Haptics can be set to `local only`. `Allow Self` is recommended for testing.
     3. Select `Proximity` from `Receiver Type`.
     4. Set target parameter to `joyconrumble1`. For right controller choose `joyconrumble2`. 

        ![componentdetails](images/help2.png)
     5. Add the above parameters to your [animator parameters](https://docs.vrchat.com/docs/animator-parameters) with default float value of 0.0. This is used by OSC to relay the status to VRCJoyCon.
        
        ![animator](images/help1.png)

**VRChat**
  1. Put controllers into pairing mode.
  2. Pair controllers manually over Bluetooth with Windows
  3. Launch vrcjoycon.exe
  4. When pairing is successful, the controllers should vibrate a few times
  5. In case of trouble, test with other joycon software first
  6. Launch **VRChat** if not already launched
     1. From the VRChat's **circular menu**, inside **settings**, inside **OSC**, choose **Enable** OSC. Additional help [here](https://docs.vrchat.com/docs/osc-overview#enabling-it).
      (*If the haptics do not work, try reset configuration option in the same menu* **ATTN.** The OSC Debug menu does not help you with debugging haptics, only output)

# Credits / components used
 - [joycon-python](https://github.com/tocoteron/joycon-python) library

# License
TODO
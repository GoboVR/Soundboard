## **Gobo’s Soundboard**

This is Gobo’s Soundboard! It’s a **WINDOWS** app that lets you play SFXS through your mic. This is a **VIBECODED** app! That means I used AI (to be specific Claude) to make this. (Because I can’t code to save my life). I made this because **EVERY** free soundboard I tried (Soundpad, Voicemod 2, Voicemod 3, etc) had either a limit on sounds or had ads. So using Claude I made this.

## **Instructions**

1. Download and install VB-Audio Cable from [https://vb-audio.com/Cable/](https://vb-audio.com/Cable/). This creates  
two virtual audio devices: CABLE Input and CABLE Output. Restart your  
PC after installing.

2. Install FFMPeg by opening CMD/Powershell and run this command:

```
winget install Gyan.FFmpeg
```

1. Go to Settings - System – Sound. Then Set your speakers to Cable Input and set your mic to Cable Output. You MIGHT have to re set it every reboot. (note: this sets it on the **WINDOWS** level if you want you can do it on app level)

2. Open The Soundboard app.

3. Set Passthrough to Cable Input.

4. Set Mic Input: to your mic.

5. Set Play Locally on: to your speakers.

6. Add your sfxs!

## **Build Instructions**

```
Idk why you would do this because there is a pre built .exe in Releases but this is how.
```

1. Make sure soundboard.py, requirements.txt, and build\_exe.bat are all in the same folder.

2. Run build\_exe.bat. It installs dependencies + PyInstaller and builds the exe for you.

3. \*When it finishes it will be in C:\\Path\\The\\Bat\\Is\\In\\dist\\ as VoiceChatSoundboard.exe

## **Troubleshooting**

- The sfxs aren’t playing in game/vc: Double check your Mic and Speakers settings are right!

- "Could not start mic passthrough": this usually means your mic and CABLE Input aren't running at the same sample rate. Open Windows Sound settings -\> your mic's Properties -\> Advanced, and CABLE Input's Properties -\> Advanced, and set both to the same rate (48000 Hz is a safe choice), then try again.

- No one hears me in game/vc but the sfxs play!: You need to turn on Passthrough!

- Everyone hears me in game/vc but when I play a sfx it makes a loud echoing sound!: You need to move to Headphones/Earbuds instead of Speakers. If you have to use Speakers Turn Off Passthrough. But if you do this no one will hear you in game. Or you can turn off Play SFX locally which will make it go away and other players will hear it but you won't. Note: If this happens press the panic button to stop it!

- mp3 files won't load: convert them to .wav

- Hotkeys won’t fire in game/app!: Run the app as admin (Windows requires elevated privileges for some games to receive global hotkeys through other apps).


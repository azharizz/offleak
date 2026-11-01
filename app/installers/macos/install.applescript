-- Copies Offleak from the disk image to ~/Applications/Offleak and runs its installer in Terminal.
set imageFolder to do shell script "dirname " & quoted form of POSIX path of (path to me)
set target to (POSIX path of (path to home folder)) & "Applications/Offleak"
display dialog "Offleak will be copied to ~/Applications/Offleak, then Terminal opens to install Python packages, models and the OBS plugins (about 10 minutes, needs internet).

Close OBS first." buttons {"Cancel", "Install"} default button "Install" with title "Install Offleak" with icon note
do shell script "mkdir -p " & quoted form of target & " && ditto " & quoted form of (imageFolder & "/Offleak") & " " & quoted form of target
tell application "Terminal"
	activate
	do script "cd " & quoted form of target & " && ./'Install Offleak.command'"
end tell

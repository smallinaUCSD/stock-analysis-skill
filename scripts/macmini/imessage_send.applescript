-- Send one iMessage: osascript imessage_send.applescript +15551234567 "text"
on run argv
	set theNumber to item 1 of argv
	set theText to item 2 of argv
	tell application "Messages"
		set theService to 1st account whose service type = iMessage
		send theText to participant theNumber of theService
	end tell
end run

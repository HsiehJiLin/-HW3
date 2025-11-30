1.Enter your nycu account to config_linuxuser.json
	{
    		"linuxuser": "your_nycu_account"
	}
	replace "your_nycu_account" with your 系計中帳號




2.Your game client uses pygame, so install it before running:

	### Windows / macOS / Linux:
    		pip install pygame

		


3.set private key and public key
	enter following command to create key
		ssh-keygen -t ed25519 -C "nycu-gamelab"

	when you see "Enter file in which to save the key (/Users/.../.ssh/id_ed25519):"
		just press enter

	when you see "Enter passphrase (empty for no passphrase):"
		just press enter

	when you see "Enter same passphrase again:"
		just press enter


	## Uploading your SSH public key (one-line command)
	Run the command that matches your OS.  
	Replace `<your_nycu_account>` with your own NYCU Linux username(系計中帳號).

	### Windows (PowerShell)
    		type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh <your_nycu_account>@linux1.cs.nycu.edu.tw "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"

	### macOS
    		cat ~/.ssh/id_ed25519.pub | ssh <your_nycu_account>@linux1.cs.nycu.edu.tw "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"

	### Linux
    		cat ~/.ssh/id_ed25519.pub | ssh <your_nycu_account>@linux1.cs.nycu.edu.tw "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"


	after finish the steps above
	enter ssh <your_nycu_account>@linux1.cs.nycu.edu.tw


	if you can login without enter your password
	means you did it right

	and enter the following command to leave the server.
		exit

4. start lobby client
	### Windows (PowerShell)
		py client.py

	### macOS/Linux
		python3 client.py

5. start Developer Client
	### Windows (PowerShell)
		py Developer_client.py

	### macOS/Linux
		python3 Developer_client.py


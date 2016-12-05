Author: Jacob Dickinson
		jdickins@uoregon.edu

# proj10-Gcal

Deployment: In the terminal, navigate to the program file and type the command “./configure”

“make run” will execute the main program.
“make database_exists” will create the database and is called in “make run”.
“make destroy” will destroy the database when you are done. 

An application, which takes in a range of date/times, followed by a prompt to the user to select applicable calendars. It then returns what free times they have within that range by comparing the range to the users selected Google calendars and finding the compliment.

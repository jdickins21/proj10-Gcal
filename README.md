Author: Jacob Dickinson
		jdickins@uoregon.edu

# proj10-Gcal

An application, which takes in a range of date/times, followed by a prompt to the user to select applicable calendars. It then returns what free times they have within that range by comparing the range to the users selected Google calendars and finding the compliment.

Deployment: In the terminal, navigate to the program file and type the command “./configure”

“make run” will execute the main program.
“make database_exists” will create the database and is called in “make run”.
“make destroy” will destroy the database when you are done. 

Proposer Directions:

First the proposer will be prompted to enter their name. Next, they will enter the days in which they wish to have the appointment,followed by  time frame. Next, the proposer will be prompted with a request to view their Google calendars. If they allow access, they will then be asked to select which calendars should be used to find free times in their schedule. When the final free times list is collected, the proposer will the be given a link to send to the individuals they want to participate in the intended event. The proposer must copy this link and send it to the intended participants through e-mail etc. The participant can now view a status page which will update with the current free times.

Participant Directions:

First the participant will be prompted to input their name. Next They will receive a request to access their Google calendars. The participant will then select which calendars define their busy times. Their free times will be calculated and they will be able to view the status page and see the most up-to-date free times.



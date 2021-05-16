# Quebec Covid-19 Vaccination Appointment finder

## Problem
Trying to get an appointment for a covid vaccine on https://portal3.clicsante.ca/ is tedious.

There is no "session reservation" system which means that you can select an available time slot, start filling up the forms and by the time you are ready, the appointment was already taken by someone else...
   
## Partial Solution
This is a simple python script that fetch the available time slots for appointments within XX km of a given postal code.

It provide the link to the establishment page. 

You still need to manually fill up the forms so you got to be quick before someone else snatch the appointment.

This is not an ideal solution but that's what I came up with in an hour or so (ideally the website would have been built better..).

## Usage
The `requests` python package is required (`pip install requests`).

Then run `python3 scan.py` with the following arguments :
```
  -p POSTAL_CODE, --postal_code POSTAL_CODE
                        Your postal code.
  -d IN_THE_NEXT, --in_the_next IN_THE_NEXT
                        Look for appointments in the next X days.
  -m MAX_DISTANCE, --max_distance MAX_DISTANCE
                        Look for appointments within X km of postal code.
```

And that's it. Hope it can help some people to get an appointment

## Warning
Please do not hammer `clicsante.ca` with this script. Use responsibly.
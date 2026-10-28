# Changelog

Earlier development notes, moved out of the README.

## Todo
1. ~~Function to average out profits hourly in both the abyss and incursion functions~~
2. ~~error input for the Incursion Module~~
3. ~~add session details into file for Incursion Module~~
4. ~~Update incursion module to limit use of Globals and start using parameters~~
5. ~~Write to file function for abyss module instead of inside Run Function for aesthetics and proper code~~

## 4/5/24 TextFile Functionality
Adding to File branch created to work on the functionality to add 
end of session reports to a text file for more advanced storage

## 4/10/24
implemented adding the session details to a Txt file at the end to keep long-term
track of profits and time spent. + Getting the hang of using branches to work on specific info and then
pulling to the main.

## 4/18/24 
Got back into doing incursion with a cool group of people in WTM
I now have an abyssal tracker that prompts for profit which should always remain a stable 31m 
and then asks for time. I am going to focus now on making an average tracker at the end of the session that shows up to tell you how 
much you made per hour.

## 4/21/24
Incursion modules Try again prompt has been updated to use 0 and 1 as well as added
an incursion ran counter like in the abyss module to keep track.

## 10/23/26
Desktop UI built with CustomTkinter (`gui.py`): live session stats, a built-in abyssal timer, ISK/hour and a
history page with a chart. Tracking logic moved into `core.py` and now saves every run to SQLite instead of
appending summaries to Sessions.txt (which can still be imported). Fixed total profit carrying over between
abyss sessions, and the terminal version now works on Linux/macOS too.

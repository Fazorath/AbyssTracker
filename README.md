Project Name: Abyssal Run Tracker

Description:
The Abyssal Run Tracker is a Python program designed to help EVE Online players track their profits and statistics from Abyssal runs. It provides a simple and user-friendly interface for entering starting ISK, ending ISK, and time spent in the Abyss. The program calculates the profit from each run and keeps a running total of profits, number of runs, and total time spent in the Abyss.

Key Features:

Input starting and ending ISK for each Abyssal run.
Track the time spent in each Abyssal run.
Calculates and displays the profit from each run.
Keeps a running total of profits, number of runs, and total time spent in the Abyss.
Error handling for invalid inputs to ensure smooth operation.
How to Use:

Run the program and follow the prompts.
Enter the starting ISK, ending ISK, and time spent for each Abyssal run.
The program will calculate the profit for each run and display it.
After each run, choose to track another Abyssal run or exit.
The program will display the total profit, number of runs, and total time spent when finished.
Contributing:
Contributions are welcome! If you find bugs or have suggestions for improvements, feel free to create an issue or submit a pull request on GitHub.

License:
This project is licensed under the MIT License.

Acknowledgements:
This project was inspired by the need for an easy-to-use tool for tracking Abyssal run profits in EVE Online. Special thanks to the EVE Online community for their feedback and support.

# Todo:
- Function to average out profits hourly in both the abyss and incursion functions
- error input for the Incursion Module
- add session details into file for Incursion Module

# 4/5/24 TextFile Functionality
Adding to File branch created to work on the functionality to add 
end of session reports to a text file for more advanced storage

# 4/10/2024
implemented adding the session details to a txt file at the end to keep long term
track of profits and time spent. + getting the hang of using branches to work on specific info and then
pulling to main.

# 4/18/2024 
Got back into doing incursion with a cool group of people in WTM
i now have an abyssal tracker that promps for profit which should always remain a stable 31m 
and then asks for time. I am going to focus now on making a average tracker at the end of the session that shows up to tell you how 
much you made per hour.

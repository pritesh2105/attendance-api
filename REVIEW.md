# REVIEW.md

List every defect you found in the starter `app/main.py` (helpers and endpoints). For each one:

| # | Where (function / line) | What is wrong | How you'd notice it (test, input, or symptom) | How you fixed it |
|---|---|---|---|---|
| 1 | In the def list_employees the skip line | The formula for page skip was wrong it was (page*page_size)  because of it the page 1 skipping the bunch page of results| i noticed after checking the GEt/employee it was showing 0 items but 6 total so i figured their was something wrong and i checked| I changed the formula by adding -1 in it making formula ((page-1)*page_size)

| 2 |At the line 36 37  |THE seconds where rounded to minutes so the punch in was getting wrong by 1 min which is wrong by R2 rule|Noticed when 9:40:1 time was punched but it was not counted as late and returning as 0|i changed the logic by not comparing first to minute and by second >600 so that it will count the lest sec|


| 3 |At def compute_work_hours|it using python round() which is not an actual round for whole number asked in R4 rule|THE punch in and punch out time difference shows it  |the python function of DEcimal with Round_half_up|


| 4 |at def compute_overtime|after leaving 10 later it should give 0 because R3 says if it is late and its is >=30 count if not then it is 0|Shift end at 18:30 punch out at 18:40|Returing the minutes only |


| 5 |Same at def compute_overtime|Shift end always built on the attendance date, so overnight shifts (22:00-06:00) got an end time 24 hours too early|shift at 22:00 to 6:00 at if punch out is at 6:45 it is giving lots of minutes|if shift_end is less than the shift_start adding one day|
Also note anything you looked at and decided was **not** a defect, and why.

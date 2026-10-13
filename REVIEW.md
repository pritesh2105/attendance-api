# REVIEW.md

List every defect you found in the starter `app/main.py` (helpers and endpoints). For each one:

| # | Where (function / line) | What is wrong | How you'd notice it (test, input, or symptom) | How you fixed it |
|---|---|---|---|---|
| 1 | In the def list_employees the skip line | The formula for page skip was wrong it was (page*page_size)  because of it the page 1 skipping the bunch page of results| i noticed after checking the GEt/employee it was showing 0 items but 6 total so i figured their was something wrong and i checked| I changed the formula by adding -1 in it making formula ((page-1)*page_size)

| 2 |At the line 36 37 minutes  |THE seconds where rounded to minutes so the punch in was getting wrong by 1 min which is wrong by R2 rule|Noticed when 9:40:1 time was punched but it was not counted as late and returning as 0|i changed the logic by not comparing first to minute and by second >600 so that it will count the lest sec|


| 3 |---|---|---|---|
Also note anything you looked at and decided was **not** a defect, and why.

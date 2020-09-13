import requests
import json
import sys
import pandas as pd
from hebrew_numbers import gematria_to_int as gim
UNAVAILABLE_TIME_FILENAME = "unavailable_times.csv"
COMPLETED_COURSES_FILENAME = "completed_courses.txt"
TIME_OFFSET = 15


lessons = {
    "\u05ea\u05e8\u05d2\u05d9\u05dc": "TA",
    "\u05e9\u05e2\u05d5\u05e8": "Lecture",
    "\u05e9\u05e2\u05d5\u05e8 \u05d5\u05ea\u05e8\u05d2\u05d9\u05dc": "Lecture and TA",
    "\u05de\u05e2\u05d1\u05d3\u05d4": "Lab"
}
def lesson_type(hebrew):
    if hebrew in lessons:
        return lessons[hebrew]
    return hebrew

def scrape(faculty, chug, maslul):
    url = f"http://moon.cc.huji.ac.il/nano/pages/wfrMaslulDetails.aspx?year=2021&faculty={faculty}&entityId={chug}&chugId={chug}&degreeCode=71&maslulId={maslul}"
    courses = []
    for table in pd.read_html(requests.get(url).text):
        try:
            if table.loc[0, 0] == "מספר הקורס":
                for i in range(len(table[0])):
                    if str(table[0][i]).isnumeric() and "א'" in str(table[3][i]):
                        courses.append((int(table[0][i]), table[1][i]))
        except:
            continue
    return courses


def parse_course(course):
    course_number = course[0]
    course_url = rf"http://moon.cc.huji.ac.il/nano/pages/wfrCourse.aspx?faculty=2&year=2021&courseId={course_number}"
    division = dict()
    reached = False  # we've reached the depndecies
    reached_number = False  # false until found the first number after started dependencies
    new_batch = True  # waiting for new batch to be created
    dependencies = []
    for table in pd.read_html(requests.get(course_url).text):
        if table.loc[0, 0] == "דרישות קדם ברמת האוניברסיטה":  # only starts the dependencies
            reached = True
        elif reached:  # if we're in the middle
            if str(table.loc[0, 0]).isnumeric():  # if this is a course number
                for item in table[0]:
                    if str(item).isnumeric():
                        reached_number = True
                        if new_batch:  # if this is in a new group
                            dependencies.append([])
                            new_batch = False
                        dependencies[-1].append(int(item))  # add it to the latest group
            elif reached_number:  # this is a non numberic one
                if "את" not in table.loc[0, 0] and "אחד" not in table.loc[0, 0]:  # this is the second non numeric one
                    reached = False  # we are done
                elif not new_batch:
                    new_batch = True
        
        elif table.loc[0, 0] == "סוג":  # if this is a valid table
            prev_lesson = None
            for i, item in enumerate(table[6]):  # for each hour-line
                # TODO : add semester B functionality later
                if item == "א'":  # if it's for the first semster
                    line = tuple((table[j][i] for j in range(6)))
                    valid = True
                    for val in line:
                        if val != val:  # val = NaN
                            valid = False
                            break
                    else:  # is NaN was found, don't add it
                        if prev_lesson is None or prev_lesson != line[0]:  # if this is a new sort of lesson
                            division[lesson_type(line[0])] = {}
                            prev_group = None
                        if prev_group is None or prev_group != line[1]:
                            division[lesson_type(line[0])][gim(line[1])] = []
                        prev_lesson, prev_group = line[:2]
                        day, start, end = line[2:5]
                        new = (gim(day), int(start.replace(":", "")), int(end.replace(":", "")))
                        division[lesson_type(prev_lesson)][gim(line[1])].append(new)  # group | day | from | to
    return division, dependencies

def collision(time1, time2):
    # time1: school, time2: uni
    if time1[0] != time2[0]:
        return False
    if time1[2] + TIME_OFFSET <= time2[2]:
        return False
    if time1[1] - TIME_OFFSET >= time2[1]:
        return False
    return True

def main():
    print("Welcome to the course-o-finder. Please make sure that your unavailable_times.csv and completed_courses.txt files are read to be used.")
    faculty = input("Please enter the faculty number (e.g. 2 for Natural Sciences) (all data needed can be found in the url to the MOON CC): ")
    chug = input("Please enter the chug number (e.g. 521 for Comp. Sc.): ")
    lane = input("Please enter the lane number (e.g. 23009 for Single Chug Comp. Sc.) (Note that it might include a random digit in the beginning): ")
    unavailable_times = []
    completed_courses = []

    with open(UNAVAILABLE_TIME_FILENAME) as file:
        for line in file:
            day, start, end = line.split(',')
            unavailable_times.append((int(day), int(start), int(end)))
            
    with open(COMPLETED_COURSES_FILENAME) as file:
        completed_courses = [int(line) for line in file]
    
    courses_data = {}
    scraped = scrape(faculty, chug, lane)
    for course in scraped:
        current_course, dependencies = parse_course(course)
        found = True
        for dependency_group in dependencies:
            for dependency in dependency_group:
                if dependency in completed_courses:  # if one dependency at least is available
                    break
            else:  # if no dependency was found in this group, it's bad
                found = False
                break
        if found:
            for bad_time in unavailable_times:
                for lesson in current_course:
                    for group in current_course[lesson]:
                        i = 0
                        group_hours = current_course[lesson][group]
                        while i < len(group_hours):
                            if collision(bad_time, group_hours[i]):
                                group_hours.pop(i)
                            else:
                                i += 1
            if len(current_course):
                for lesson in current_course:
                    if not current_course[lesson]:
                        break
                else:
                    courses_data[course[0]] = current_course

    with open("pretty.json", "w") as file:
        json.dump(courses_data, file, indent=4)
    
    with open("shortened.json", "w") as file:
        json.dump([x for x in courses_data], file, indent=4)
    
    if input("Do you want the list of available courses to be printed (y/n)? ") == "y":
        for course in courses_data:
            print(course)
    
if __name__ == "__main__":
    main()
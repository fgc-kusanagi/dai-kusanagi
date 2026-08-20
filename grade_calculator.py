A_GRADE_MINIMUM = 90
B_GRADE_MINIMUM = 80
C_GRADE_MINIMUM = 70
D_GRADE_MINIMUM = 60


def calculate_average(scores):
    if not scores:
        return 0.0

    total_score = 0
    for score in scores:
        total_score = total_score + score

    return total_score / len(scores)


def determine_grade(average_score):
    if average_score >= A_GRADE_MINIMUM:
        return "A"
    elif average_score >= B_GRADE_MINIMUM:
        return "B"
    elif average_score >= C_GRADE_MINIMUM:
        return "C"
    elif average_score >= D_GRADE_MINIMUM:
        return "D"
    return "F"


def display_result(average_score, grade):
    print("Average:", average_score)
    print("Grade:", grade)


def f(scores):
    average_score = calculate_average(scores)
    grade = determine_grade(average_score)
    display_result(average_score, grade)
    return grade

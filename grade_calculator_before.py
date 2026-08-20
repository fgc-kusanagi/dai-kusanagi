def f(d):
    t = 0
    for i in d:
        t = t + i

    a = t / len(d)

    if a >= 90:
        r = "A"
    elif a >= 80:
        r = "B"
    elif a >= 70:
        r = "C"
    elif a >= 60:
        r = "D"
    else:
        r = "F"

    print("Average:", a)
    print("Grade:", r)
    return r

import math


def primelist(x):
    primes = [True for i in range(0,x+1)]
    i = 2
    while i*i <= x:
        if primes[i]:
            for j in range(2,x//i+1):
                primes[j*i] = False
        i += 1
    res = []
    for i in range(2,x+1):
        if primes[i] == True:
            res.append(i)
    return res
            
primes = primelist(10000)


def factorize(x,num):# return true when x has prime factors more than or equal to 3
    global primes
    if num == 2:
        for i in primes:#check 8,27 etc..
            if i**3 == x:
                return False
        return True

    for i in primes:
        if i <= x//2:
            if x % i == 0:
                return factorize(x//i,num+1)
    return False


def step2(int:int):
    flag = True
    for i in range(2,int//2):
            x = i
            y = int-i
            if not factorize(x*y,0):
                flag = False
    return flag

res1 = []
for sum in range(4,100):
    if step2(sum):
        res1.append(sum)
print("From step 1 and 2, x+y lies in")
print(res1)
def step3(b): #xy = b
    sum = 0
    for i in range(2,int(math.sqrt(b))+1):
        if b % i == 0:
            x = i
            y = b // i
            if step2(x+y) == True:
                sum += 1
                t1 = (x,y)

    if sum == 1:
        return (True,t1)
    else:
        return (False,None)


for i in res1:
    sum = 0
    for j in range(2,i//2):
        x = j
        y = i - j
        result,pair = step3(x*y)
        if result == True:
            sum += 1
            t1 = pair

    if sum == 1:
        print(i,t1)
            

    





            

numbuild = int(input())
numqueries = int(input())
buildings = [0 for i in range(numbuild)]
for _ in range(numbuild):
    buildings[_]=int(input())

for _ in range(numqueries):
    if int(input()) == 1:
        k = int(input())
        x = int(input())
        buildings[k-1]=x
    else:
        k = int(input())
        min = buildings[k-1]
        for i in range(len(buildings)):
            price = buildings[i] + abs(i-k+1)
            if price < min:
                min = price
        print(min)








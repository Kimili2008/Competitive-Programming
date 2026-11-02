print("a")
numcities = int(input())

roads = [[]*2 for _ in range(numcities-1)]

def next_letter(letter):
    if 'a' <= letter <= 'z':  # 小写字母处理
        return chr(ord(letter) + 1) if letter != 'z' else 'a'
    elif 'A' <= letter <= 'Z':  # 大写字母处理
        return chr(ord(letter) + 1) if letter != 'Z' else 'A'




for i in range(numcities):
    a = int(input())
    b= int(input())
    roads[i][0] = a
    roads[i][1] = b

cities = [ 0 for _ in range(numcities)]
for i in roads:
    cities[i[0]] += 1
    cities[i[1]] += 1
rank = [ '' for _ in range(numcities)]
for i in range(len(cities)):
    if cities[i] == 1:
        rank[i] = 'A'

letter = 'B'
while num < 27:














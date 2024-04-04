animelist = ['Naruto', 'Bleach', 'One Piece', 'Dragon Ball Z', 'Attack on Titan', 'My Hero Academia', 'Tokyo Ghoul', 'Death Note', 'Sword Art Online', 'One Punch']
print('Welcome to Anime Picker!')

exit = False
while(exit != True):
    num = int(input('Choose a number between 1 - 10: '))
    print(f"You got: {animelist[num-1]}")
    Qexit = input('Would you like to choose another number? ').upper()
    if Qexit == 'NO':
        print('\nThank you for using Anime Picker!')
        exit = True



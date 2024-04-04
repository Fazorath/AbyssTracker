
def profitCalc(startingInv,AfterInv):
    profit = print(f"Profit is going to be {AfterInv-startingInv}")

def startingInven():
    before = int(input("Isk Total before Abyss: "))
    return before

def afterInven():
    after = int(input("Isk Total after Abyss: "))
    return after

def main():
    startInv = startingInven()
    afterInv = afterInven()
    print(profitCalc(startInv,afterInv))

if __name__ == "__main__":
    main()

        
     
from .dearbagplayer import DearBagPlayer
import sys

def main():
    app = DearBagPlayer()
    app.run()
    return 0

if __name__ == '__main__':
    sys.exit(main())

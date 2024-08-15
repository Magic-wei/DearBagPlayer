from .dearbagplayer import DearBagPlayer

VERSION = "0.2.2"

# Entry point
def main():
    app = DearBagPlayer()
    app.run()
    return 0

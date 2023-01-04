from .dearbagplayer import DearBagPlayer

VERSION = "0.1.0"


# Entry point
def main():
    app = DearBagPlayer()
    app.run()


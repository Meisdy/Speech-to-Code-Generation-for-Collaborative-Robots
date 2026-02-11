from pipeline import Controller
from gui import UserGUI


def main() -> None:
    controller = Controller()
    gui = UserGUI(on_record_start=controller.on_start, on_record_stop=controller.on_stop)

    controller.set_gui(gui)  # Give controller access to GUI
    gui.run()


if __name__ == "__main__":
    main()
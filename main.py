from pipeline import Controller
from gui import UserGUI


def main() -> None:
    controller = Controller()
    gui = UserGUI(
        on_record_start=controller.start_recording,
        on_record_stop=controller.start_execution
    )
    controller.set_gui(gui)

    # Register cleanup on closing the window. Not sure if this is needed, but cant hurt to be safe
    gui.on_window_close(controller.cleanup)


    # Start the GUI event loop, ensuring cleanup is called on exit
    try:
        gui.run()
    finally:
        controller.cleanup()  # Always runs, even on exception


if __name__ == "__main__":
    main()
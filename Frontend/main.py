import logging
from logging_setup import setup_logging, GuiHandler
from gui import UserGUI
from pipeline import Controller


def main() -> None:

    # Initialize logging first to capture all events
    logger = setup_logging()
    logger.info("Application starting")

    # Initialize controller and GUI, linking them together
    controller = Controller()
    gui = UserGUI(
        on_record_start=controller.start_recording,
        on_record_stop=controller.start_execution
    )
    controller.set_gui(gui)

    # Attach GUI handler after gui exists
    gui_handler = GuiHandler(gui, level=logging.INFO)
    logging.getLogger("cobot").addHandler(gui_handler)

    # Register cleanup on closing the window. Not sure if this is needed, but cant hurt to be safe
    gui.on_window_close(controller.cleanup)

    # Start the GUI event loop, ensuring cleanup is called on exit
    try:
        logger.info('Application ready')
        gui.run()
    finally:
        controller.cleanup()  # Always runs, even on exception
        logger.info("Application shutting down")


if __name__ == "__main__":
    main()
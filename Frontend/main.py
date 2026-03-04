import logging
from Frontend.logging_setup import setup_logging, GuiHandler
from Frontend.gui import UserGUI
from Frontend.pipeline import Controller


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

    # Register window-close handler — this is the primary cleanup path
    gui.on_window_close(controller.cleanup)

    try:
        logger.info("Application ready")
        gui.run()
    finally:
        controller.cleanup()  # Fallback: covers crashes and non-window-close exits
        logger.info("Application shutting down")


if __name__ == "__main__":
    main()
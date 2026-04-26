import argparse
import sys
import os
import logging

# Ensure project root is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gui.app import main as launch_gui

def main():
    parser = argparse.ArgumentParser(description="Marketplace Scraper v1.0")
    parser.add_argument("--gui", action="store_true", default=True, help="Launch the GUI interface (default)")
    parser.add_argument("--cli", action="store_true", help="Launch CLI mode (not fully implemented in v1.0)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    if args.cli:
        print("CLI Mode: Please use the GUI for now as CLI automation is planned for future updates.")
        sys.exit(0)
    
    # Default: Launch GUI
    try:
        launch_gui()
    except Exception as e:
        logging.error(f"Failed to launch application: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

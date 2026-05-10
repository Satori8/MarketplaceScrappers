import tkinter as tk
import os
import sys
import customtkinter as ctk

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.main_window import MainWindow
from db.database import Database

def main():
    db = Database()
    db.initialize()
    
    root = ctk.CTk()
    app = MainWindow(root, db=db)
    app.pack(fill="both", expand=True)
    root.mainloop()

if __name__ == "__main__":
    main()

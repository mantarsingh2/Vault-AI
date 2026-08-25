from PySide6.QtWidgets import QMainWindow


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Vault AI")
        self.resize(1000, 700)
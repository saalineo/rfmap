import sys

from PyQt6.QtWidgets import QApplication

from wifi.networking import RSSIWorker
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Wavey")

    window = MainWindow()
    window.showMaximized()

    rssi_worker = RSSIWorker()
    rssi_worker.rssi_updated.connect(window.update_rssi)
    rssi_worker.source_changed.connect(window.update_source)
    rssi_worker.ssid_updated.connect(window.update_ssid)
    rssi_worker.devices_updated.connect(window.update_devices)
    rssi_worker.start()

    app.aboutToQuit.connect(rssi_worker.stop)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

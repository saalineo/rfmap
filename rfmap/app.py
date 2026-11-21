import sys

from PyQt6.QtWidgets import QApplication

from rfmap.wifi.worker import RSSIWorker
from rfmap.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("RFMap")

    window = MainWindow()
    window.showMaximized()

    rssi_worker = RSSIWorker()
    rssi_worker.rssi_updated.connect(window.update_rssi)
    rssi_worker.source_changed.connect(window.update_source)
    rssi_worker.ssid_updated.connect(window.update_ssid)
    rssi_worker.devices_updated.connect(window.update_devices)
    window.attach_rssi_worker(rssi_worker)
    rssi_worker.start()

    exit_code = app.exec()
    rssi_worker.stop()
    rssi_worker.wait()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

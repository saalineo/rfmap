import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from security.ap_scanner import IwScanner, SimulatedScanner


def main():
    scanner_env = os.environ.get("SENTINEL_SCANNER")
    if scanner_env:
        scanner = IwScanner()
        print(f"Using fixture: {scanner_env}")
    else:
        scanner = SimulatedScanner()
        print("Using simulated scanner")

    observations = scanner.scan()
    print(f"{'SSID':<20} {'BSSID':<20} {'Ch':>3} {'Sec':<15} {'RSSI':>6}")
    print("-" * 68)
    for obs in observations:
        ssid = obs.ssid if obs.ssid else "(hidden)"
        print(f"{ssid:<20} {obs.bssid:<20} {obs.channel:>3} {obs.security:<15} {obs.rssi:>6.1f}")


if __name__ == "__main__":
    main()
import math


def make_sample(x, y, rssi, bssid="aa:bb:cc:dd:ee:02", channel=6):
    from rfmap.models import SurveySample
    return SurveySample(bssid=bssid, x=x, y=y, rssi=rssi, channel=channel)


def ring_samples(true_x, true_y, n, dist=15.0, bssid="aa:bb:cc:dd:ee:02", channel=6):
    samples = []
    for i in range(n):
        angle = i * 2 * math.pi / n
        x = true_x + dist * math.cos(angle)
        y = true_y + dist * math.sin(angle)
        d = math.sqrt((x - true_x) ** 2 + (y - true_y) ** 2)
        rssi = -30.0 - 10.0 * 2.4 * math.log10(max(d, 1.0))
        samples.append(make_sample(x, y, rssi, bssid=bssid, channel=channel))
    return samples

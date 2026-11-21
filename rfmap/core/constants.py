"""Grid and RF-propagation constants shared by the map and localization code."""

GRID_SIZE = 100


CELL_METERS = 0.3


TX_POWER_DBM = -30.0


PATH_LOSS_EXPONENT = 2.4


D0 = 1.0


WALL_ATTENUATION = {
    "Drywall": 3.0,
    "Brick": 12.0,
    "Reinforced Concrete": 25.0,
}

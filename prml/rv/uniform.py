import numpy as np

from prml.rv.rv import RandomVariable


class Uniform(RandomVariable):
    """Random variable that follows a uniform distribution.

    p(x|a, b)
    = 1 / ((b_0 - a_0) * (b_1 - a_1)) if a <= x <= b else 0
    """

    def __init__(self, low, high):
        """Initialize a uniform distribution.

        Parameters
        ----------
        low : int, float, or np.ndarray
            lower boundary
        high : int, float, or np.ndarray
            higher boundary
        """
        super().__init__()
        low = np.asarray(low)
        high = np.asarray(high)
        assert low.shape == high.shape
        assert (low <= high).all()
        self.low = low
        self.high = high
        self.value = 1 / np.prod(high - low)

    @property
    def low(self):
        """Lower bound of the random variable."""
        return self.parameter["low"]

    @low.setter
    def low(self, low):
        self.parameter["low"] = low

    @property
    def high(self):
        """Higher bound of the random variable."""
        return self.parameter["high"]

    @high.setter
    def high(self, high):
        self.parameter["high"] = high

    @property
    def ndim(self):
        """Rank of the random variable."""
        return self.low.ndim

    @property
    def size(self):
        """Number of elements in the random variable."""
        return self.low.size

    @property
    def shape(self):
        """Shape of the random variable."""
        return self.low.shape

    @property
    def mean(self):
        """Mean value of the random variable."""
        return 0.5 * (self.low + self.high)

    def _pdf(self, x):
        higher = np.logical_and.reduce(x >= self.low, 1)
        lower = np.logical_and.reduce(x <= self.high, 1)
        return self.value * np.logical_and(higher, lower)

    def _draw(self, sample_size=1):
        u01 = np.random.uniform(size=(sample_size,) + self.shape)
        return u01 * (self.high - self.low) + self.low

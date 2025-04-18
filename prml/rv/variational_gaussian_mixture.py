import numpy as np
from scipy.special import digamma, gamma, logsumexp

from prml.rv.rv import RandomVariable


class VariationalGaussianMixture(RandomVariable):

    def __init__(
        self,
        n_components=1,
        alpha0=None,
        m0=None,
        W0=1.,
        dof0=None,
        beta0=1.,
    ):
        """Initialize variational gaussian mixture model.

        Parameters
        ----------
        n_components : int
            maximum numnber of gaussian components
        alpha0 : float
            parameter of prior dirichlet distribution
        m0 : float
            mean parameter of prior gaussian distribution
        W0 : float
            mean of the prior Wishart distribution
        dof0 : float
            number of degrees of freedom of the prior Wishart distribution
        beta0 : float
            prior on the precision distribution
        """
        super().__init__()
        self.n_components = n_components
        if alpha0 is None:
            self.alpha0 = 1 / n_components
        else:
            self.alpha0 = alpha0
        self.m0 = m0
        self.W0 = W0
        self.dof0 = dof0
        self.beta0 = beta0

    def _init_params(self, x):
        sample_size, self.ndim = x.shape
        self.alpha0 = np.ones(self.n_components) * self.alpha0
        if self.m0 is None:
            self.m0 = np.mean(x, axis=0)
        else:
            self.m0 = np.zeros(self.ndim) + self.m0
        self.W0 = np.eye(self.ndim) * self.W0
        if self.dof0 is None:
            self.dof0 = self.ndim

        self.component_size = sample_size / self.n_components + np.zeros(self.n_components)
        self.alpha = self.alpha0 + self.component_size
        self.beta = self.beta0 + self.component_size
        indices = np.random.choice(sample_size, self.n_components, replace=False)
        self.mu = x[indices]
        self.W = np.tile(self.W0, (self.n_components, 1, 1))
        self.dof = self.dof0 + self.component_size

    @property
    def alpha(self):
        """Alpha parameter."""
        return self.parameter["alpha"]

    @alpha.setter
    def alpha(self, alpha):
        self.parameter["alpha"] = alpha

    @property
    def beta(self):
        """Beta parameter."""
        return self.parameter["beta"]

    @beta.setter
    def beta(self, beta):
        self.parameter["beta"] = beta

    @property
    def mu(self):
        """Mean parameter of posterior Wishart distribution."""
        return self.parameter["mu"]

    @mu.setter
    def mu(self, mu):
        self.parameter["mu"] = mu

    @property
    def W(self):
        """Weight parameter."""
        return self.parameter["W"]

    @W.setter
    def W(self, W):
        self.parameter["W"] = W

    @property
    def dof(self):
        """Degree of freedom."""
        return self.parameter["dof"]

    @dof.setter
    def dof(self, dof):
        self.parameter["dof"] = dof

    def get_params(self):
        """Get parameters."""
        return self.alpha, self.beta, self.mu, self.W, self.dof

    def _fit(self, x, iter_max=100):
        self._init_params(x)
        for _ in range(iter_max):
            params = np.hstack([p.flatten() for p in self.get_params()])
            r = self._variational_expectation(x)
            self._variational_maximization(x, r)
            if np.allclose(params, np.hstack([p.flatten() for p in self.get_params()])):
                break

    def _variational_expectation(self, x):
        d = x[:, None, :] - self.mu
        maha_sq = -0.5 * (
            self.ndim / self.beta
            + self.dof * np.sum(
                np.einsum("kij,nkj->nki", self.W, d) * d, axis=-1))
        ln_pi = digamma(self.alpha) - digamma(self.alpha.sum())
        ln_Lambda = digamma(0.5 * (self.dof - np.arange(self.ndim)[:, None])).sum(axis=0) + self.ndim * np.log(2) + np.linalg.slogdet(self.W)[1]
        ln_r = ln_pi + 0.5 * ln_Lambda + maha_sq
        ln_r -= logsumexp(ln_r, axis=-1)[:, None]
        r = np.exp(ln_r)
        return r

    def _variational_maximization(self, x, r):
        self.component_size = r.sum(axis=0)
        Xm = (x.T.dot(r) / self.component_size).T
        d = x[:, None, :] - Xm
        S = np.einsum('nki,nkj->kij', d, r[:, :, None] * d) / self.component_size[:, None, None]
        self.alpha = self.alpha0 + self.component_size
        self.beta = self.beta0 + self.component_size
        self.mu = (self.beta0 * self.m0 + self.component_size[:, None] * Xm) / self.beta[:, None]
        d = Xm - self.m0
        self.W = np.linalg.inv(
            np.linalg.inv(self.W0)
            + (self.component_size * S.T).T
            + (self.beta0 * self.component_size * np.einsum('ki,kj->kij', d, d).T / (self.beta0 + self.component_size)).T)
        self.dof = self.dof0 + self.component_size

    def classify(self, x):
        """Index of highest posterior of the latent variable.

        Parameters
        ----------
        x : (sample_size, ndim) ndarray
            input
        Returns
        -------
        output : (sample_size, n_components) ndarray
            index of maximum posterior of the latent variable
        """
        return np.argmax(self._variational_expectation(x), 1)

    def classify_proba(self, x):
        """Compute posterior of the latent variable.

        Parameters
        ----------
        x : (sample_size, ndim) ndarray
            input
        Returns
        -------
        output : (sample_size, n_components) ndarray
            posterior of the latent variable
        """
        return self._variational_expectation(x)

    def student_t(self, x):
        """Student's t probability distribution function."""
        nu = self.dof + 1 - self.ndim
        L = (nu * self.beta * self.W.T / (1 + self.beta)).T # noqa
        d = x[:, None, :] - self.mu
        maha_sq = np.sum(np.einsum('nki,kij->nkj', d, L) * d, axis=-1)
        return (
            gamma(0.5 * (nu + self.ndim))
            * np.sqrt(np.linalg.det(L))
            * (1 + maha_sq / nu) ** (-0.5 * (nu + self.ndim))
            / (gamma(0.5 * nu) * (nu * np.pi) ** (0.5 * self.ndim)))

    def _pdf(self, x):
        return (self.alpha * self.student_t(x)).sum(axis=-1) / self.alpha.sum()

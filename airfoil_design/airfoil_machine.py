# DEFINIZIONE FUNZIONI
from math import sin, radians, pi, ceil
def scelta_profilo(dati):
    profilo = dati["profilo"]
    tmax_c = dati["tmax_c"]
    sigma_prog = dati["sigma_prog"]
    return profilo, tmax_c, sigma_prog
def calcola_diffusion_factor(dati):
    W1 = dati["W1"]
    W2 = dati["W2"]
    beta1 = radians(dati["beta1"])
    beta2 = radians(dati["beta2"])
    sigma = dati["sigma_prog"]
    delta_Wu = abs(W2*sin(beta2)-W1*sin(beta1))
    D = 1 - W2/W1 + delta_Wu/(2*sigma*W1)
    return D

def curvatura_iniziale(dati):
    beta1 = dati["beta1"]
    beta2 = dati["beta2"]

    theta0 = beta1 - beta2

    return theta0

def calcola_incidenza_lieblein(theta, i0_10, Kti, Ksh, n):
    i_rif = Ksh * Kti * i0_10 + n * theta

    return i_rif

def calcola_deviazione_lieblein(theta, delta0_10, m, b, sigma, Kdelta_t):
    delta = Kdelta_t * delta0_10 + (m / sigma**b) * theta

    return delta

def curvatura_corretta(beta1, beta2, incidenza, deviazione):
    theta1 = beta1 - beta2 - incidenza + deviazione

    return theta1

def convergenza_curvatura(theta1, beta1, beta2,
                          i0_10, Kti, Ksh, n,
                          delta0_10, m, b, sigma, Kdelta_t,
                          epsilon, max_iter):

    theta = theta1
    iterazione = 0

    while iterazione < max_iter:

        i = calcola_incidenza_lieblein(theta, i0_10, Kti, Ksh, n)

        delta = calcola_deviazione_lieblein(
            theta, delta0_10, m, b, sigma, Kdelta_t
        )

        theta_nuova = curvatura_corretta(beta1, beta2, i, delta)

        iterazione += 1

        if abs(theta_nuova - theta) < epsilon:
            return theta_nuova, i, delta, iterazione

        theta = theta_nuova

    raise ValueError("Convergenza della curvatura non raggiunta")

def dimensionamento_geometrico(rtip, rhub, rm, AR, sigma_prog):

    if not (2 < AR < 2.5):
        raise ValueError("Aspect Ratio fuori dai limiti")

    if not (0 < rhub < rm < rtip):
        raise ValueError("Raggi non validi")

    if sigma_prog <= 0:
        raise ValueError("Solidita non valida")

    h = rtip - rhub

    c = h / AR

    sprog = c / sigma_prog

    Z = ceil(2 * pi * rm / sprog)

    delta_phi = 360 / Z

    seff = 2 * pi * rm / Z

    sigma_eff = c / seff

    return h, c, sprog, Z, delta_phi, seff, sigma_eff

def calcola_calettamento(beta1, beta2, i_eff, delta_eff):

    gamma = 90 - (beta1 + beta2 - i_eff - delta_eff) / 2

    return gamma


def verifica_aerodinamica_finale(D_eff, de_haller, D_max, de_haller_min):

    verifica_D = D_eff <= D_max
    verifica_de_haller = de_haller >= de_haller_min

    requisiti_soddisfatti = verifica_D and verifica_de_haller

    return requisiti_soddisfatti

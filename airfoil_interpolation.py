from scipy.interpolate import interp1d

def interpola_curva(angoli, valori, angolo_richiesto):
    funzione = interp1d(angoli, valori, kind="linear", bounds_error=True)

    risultato = float(funzione(angolo_richiesto))

    return risultato


def interpola_2d(punti, angolo, sigma):

    solidita = sorted(set(s for a, s, v in punti))
    valori = []

    for s in solidita:
        curva = sorted((a, v) for a, ss, v in punti if ss == s)

        angoli = [a for a, v in curva]
        risultati = [v for a, v in curva]

        valore = interpola_curva(angoli, risultati, angolo)
        valori.append(valore)


    if sigma < solidita[0]:
        if sigma < 0.25:
            raise ValueError(
                "Solidita troppo bassa per l'estrapolazione"
            )

        return valori[0] + (
            (sigma - solidita[0])
            * (valori[1] - valori[0])
            / (solidita[1] - solidita[0])
        )

    return interpola_curva(solidita, valori, sigma)


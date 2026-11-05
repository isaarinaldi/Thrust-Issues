# COLLEGAMENTO INPUT PRECEDENTI
def prepara_input_airfoil(triangles, config):

    mean = triangles["Mean"]
    hub = triangles["Hub"]
    tip = triangles["Tip"]

    dati = config.copy()

    # VELOCITA
    dati["C1"] = mean["c1"]
    dati["C2"] = mean["c2"]
    dati["W1"] = mean["w1"]
    dati["W2"] = mean["w2"]

    # ANGOLI
    dati["beta1"] = 90.0 - mean["beta1"]
    dati["beta2"] = 90.0 - mean["beta2"]

    # MACH
    dati["Ma"] = mean["Ma1"]

    # GEOMETRIA
    dati["rtip"] = tip["radius"]
    dati["rhub"] = hub["radius"]
    dati["rm"] = mean["radius"]

    return dati

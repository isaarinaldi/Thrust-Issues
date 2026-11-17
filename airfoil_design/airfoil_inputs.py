"""Convert preliminary rotor velocity triangles to NACA 65 design inputs.

`geometry.calculate_velocity_triangles` uses beta measured from the tangent.
The airfoil module uses beta measured from the machine axis.  Passing the
angle without converting it corrupts incidence and diffusion calculations.
"""


def prepara_input_airfoil(
    triangles,
    config,
    *,
    speed_of_sound=None,
    air_density=None,
    dynamic_viscosity=None,
):
    mean = triangles["Mean"]
    hub = triangles["Hub"]
    tip = triangles["Tip"]

    dati = dict(config)

    # Velocita' [m/s] alla sezione media.
    dati["C1"] = mean["c1"]
    dati["C2"] = mean["c2"]
    dati["W1"] = mean["w1"]
    dati["W2"] = mean["w2"]

    # La geometria usa beta dalla tangente; le carte Lieblein, dall'asse.
    dati["beta1"] = 90.0 - mean["beta1"]
    dati["beta2"] = 90.0 - mean["beta2"]

    # Raggi del rotore (geometria gia' verificata per continuita').
    dati["rtip"] = tip["radius"]
    dati["rhub"] = hub["radius"]
    dati["rm"] = mean["radius"]

    # Mach RELATIVO in ingresso al rotore, non Mach assoluto.
    if speed_of_sound is not None:
        if speed_of_sound <= 0:
            raise ValueError("speed_of_sound deve essere positivo.")
        dati["Ma"] = mean["w1"] / speed_of_sound
    elif "Ma1" in mean:
        # Compatibilita' con i dati precedenti, se presenti.
        dati["Ma"] = mean["Ma1"]

    # Reynolds relativo riferito alla corda preliminare c=(rtip-rhub)/AR.
    # In assenza di proprieta' fisiche, conserva il valore della config.
    if air_density is not None or dynamic_viscosity is not None:
        if air_density is None or dynamic_viscosity is None:
            raise ValueError("Re richiede sia densita' che viscosita'.")
        AR = float(dati["AR"])
        if air_density <= 0 or dynamic_viscosity <= 0 or AR <= 0:
            raise ValueError("Densita', viscosita' e AR devono essere positivi.")
        c = (dati["rtip"] - dati["rhub"]) / AR
        dati["Re"] = air_density * mean["w1"] * c / dynamic_viscosity

    if "Ma" not in dati:
        raise ValueError("Mach mancante: indicare speed_of_sound o Ma1.")

    return dati

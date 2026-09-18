from __future__ import annotations

from config.settings import MAX_EV_SANITY, MIN_EV_THRESHOLD


def remove_vig_three_way(home: float, draw: float, away: float) -> tuple[float, float, float]:
    """
    Calcula las probabilidades reales desmargenadas (No-Vig 3-Way) para el mercado 1X2 (Moneyline).

    Fórmula:
        Suma_inversas = (1 / home) + (1 / draw) + (1 / away)
        P_fair_home = (1 / home) / Suma_inversas
        P_fair_draw = (1 / draw) / Suma_inversas
        P_fair_away = (1 / away) / Suma_inversas

    Args:
        home (float): Cuota decimal opción Local (1).
        draw (float): Cuota decimal opción Empate (X).
        away (float): Cuota decimal opción Visitante (2).

    Returns:
        tuple[float, float, float]: (P_fair_home, P_fair_draw, P_fair_away).

    Raises:
        ValueError: Si alguna cuota es <= 1.0.
    """
    if home <= 1.0 or draw <= 1.0 or away <= 1.0:
        raise ValueError("Las cuotas 3-way deben ser estrictamente mayores a 1.0")

    inv_h = 1.0 / home
    inv_d = 1.0 / draw
    inv_a = 1.0 / away
    sum_inv = inv_h + inv_d + inv_a

    return inv_h / sum_inv, inv_d / sum_inv, inv_a / sum_inv


def remove_vig_two_way(odd_a: float, odd_b: float) -> tuple[float, float]:
    """
    Calcula las probabilidades reales desmargenadas (No-Vig 2-Way) para mercados de 2 opciones (Totales 2.5, BTTS).

    Fórmula:
        Suma_inversas = (1 / odd_a) + (1 / odd_b)
        P_fair_a = (1 / odd_a) / Suma_inversas
        P_fair_b = (1 / odd_b) / Suma_inversas

    Args:
        odd_a (float): Cuota decimal opción A.
        odd_b (float): Cuota decimal opción B.

    Returns:
        tuple[float, float]: (P_fair_a, P_fair_b).

    Raises:
        ValueError: Si alguna cuota es <= 1.0.
    """
    if odd_a <= 1.0 or odd_b <= 1.0:
        raise ValueError("Las cuotas 2-way deben ser estrictamente mayores a 1.0")

    inv_a = 1.0 / odd_a
    inv_b = 1.0 / odd_b
    sum_inv = inv_a + inv_b

    return inv_a / sum_inv, inv_b / sum_inv


def calculate_ev(bookmaker_odd: float, fair_prob: float) -> float:
    """
    Calcula el Valor Esperado (+EV) matemático de una cuota recreativa.

    Fórmula:
        EV = (bookmaker_odd * fair_prob) - 1

    Args:
        bookmaker_odd (float): Cuota ofrecida por la casa recreativa.
        fair_prob (float): Probabilidad justa calculada sin vig (0.0 a 1.0).

    Returns:
        float: Valor Esperado (+EV). Por ejemplo, 0.05 para +5% EV.
    """
    if bookmaker_odd <= 1.0:
        raise ValueError("La cuota de la casa recreativa debe ser mayor a 1.0")
    if not (0.0 <= fair_prob <= 1.0):
        raise ValueError("La probabilidad justa debe estar entre 0.0 y 1.0")

    return (bookmaker_odd * fair_prob) - 1.0


def is_value_bet(
    bookmaker_odd: float,
    fair_prob: float,
    min_ev: float = MIN_EV_THRESHOLD,
    max_ev_sanity: float = MAX_EV_SANITY,
) -> tuple[bool, float]:
    """
    Determina si una cuota supera el umbral de EV (+4.0%) y cumple el Sanity Check (EV <= +20.0%).

    Args:
        bookmaker_odd (float): Cuota ofrecida por la casa recreativa.
        fair_prob (float): Probabilidad justa calculada desde la casa sharp (Pinnacle).
        min_ev (float): Umbral mínimo de EV requerida (0.04 -> +4.0% EV).
        max_ev_sanity (float): Umbral máximo de EV razonable (0.20 -> +20.0% EV).

    Returns:
        tuple[bool, float]: (Es_Apuesta_De_Valor_Valida, Porcentaje_EV).
    """
    ev = calculate_ev(bookmaker_odd, fair_prob)
    ev_pct = ev * 100.0

    # Sanity check: si EV > +20%, descartar por anomalía de datos o desajuste de línea
    if ev > max_ev_sanity:
        return (False, ev_pct)

    return (ev >= min_ev, ev_pct)


# Aliases de compatibilidad
calculate_no_vig_prob = remove_vig_two_way
is_value_opportunity = lambda book_odd, fair_prob, threshold=MIN_EV_THRESHOLD: is_value_bet(book_odd, fair_prob, threshold)[0]

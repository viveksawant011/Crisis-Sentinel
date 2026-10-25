"""
Offline tests for What-If simulation formulas and boundary conditions.
"""

from whatif import simulate_whatif


def test_hand_calculated_case_po10482():
    """Validates: D = 28, f = 1.0 vs f = 0.5 for Taiwan semiconductor PO10482."""
    res = simulate_whatif(
        country="Taiwan",
        category="semiconductor",
        disruption_days=28,
        capacity_offline_pct=100.0,
        apply_reroute=True,
    )

    po = next((p for p in res["pos"] if p["po_id"] == "PO10482"), None)
    assert po is not None, "PO10482 must be returned"

    # Stockout day: 18000 / 1650 = 10.9 days
    assert abs(po["stockout_day"] - 10.9) <= 0.1

    # Baseline: shortfall = 1650 * 28 - 18000 = 28200 units, stoppage = 17.1 days
    assert abs(po["baseline"]["shortfall_units"] - 28200) <= 50
    assert abs(po["baseline"]["stoppage_days"] - 17.1) <= 0.2
    assert abs(po["baseline"]["value_at_risk_eur"] - 676800.0) <= 2000.0

    # With reroute (L = 18): shortfall = 1650 * 18 - 18000 = 11700, stoppage = 7.1 days
    assert abs(po["with_reroute"]["shortfall_units"] - 11700) <= 50
    assert abs(po["with_reroute"]["stoppage_days"] - 7.1) <= 0.2
    assert abs(po["with_reroute"]["value_at_risk_eur"] - 280800.0) <= 2000.0


def test_whatif_half_capacity():
    """D = 28, f = 0.5: depletion is halved."""
    res = simulate_whatif(
        country="Taiwan",
        category="semiconductor",
        disruption_days=28,
        capacity_offline_pct=50.0,
        apply_reroute=True,
    )
    po = next((p for p in res["pos"] if p["po_id"] == "PO10482"), None)
    assert po is not None

    # stockout: 18000 / (1650 * 0.5) = 21.8 days
    assert abs(po["stockout_day"] - 21.8) <= 0.2
    assert abs(po["baseline"]["shortfall_units"] - 5100) <= 50
    assert abs(po["baseline"]["stoppage_days"] - 6.2) <= 0.2
    # Reroute with L = 18 < stockout day (21.8) -> 0 shortfall
    assert po["with_reroute"]["shortfall_units"] == 0
    assert po["with_reroute"]["stoppage_days"] == 0.0


def test_whatif_zero_capacity_loss():
    """f = 0: no depletion, zero shortfall everywhere."""
    res = simulate_whatif(
        country="Taiwan",
        category="semiconductor",
        disruption_days=28,
        capacity_offline_pct=0.0,
    )
    assert res["totals"]["baseline"]["value_at_risk_eur"] == 0.0
    assert res["totals"]["baseline"]["units_short"] == 0
    assert res["totals"]["baseline"]["max_stoppage_days"] == 0.0
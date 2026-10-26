"""
Offline tests for the honesty-critical behaviour: no network, models and Tavily are stubbed.
Run: pytest -q
"""
import json

import pytest
from fastapi.testclient import TestClient

import api
import investigator
import strategist
from critic import critique_and_verify, run_deterministic_checks
from engine import evaluate_erp_exposure
from whatif import simulate_whatif

client = TestClient(api.app)


# ---------------------------------------------------------------- helpers
def _exposure():
    return evaluate_erp_exposure("Taiwan", "semiconductor")


def _first_alt(exp):
    return exp["mitigation_alternatives"][0]


# ---------------------------------------------------------------- investigator
class FakeTavily:
    def __init__(self, n=3):
        self.calls = []
        self.n = n

    def search(self, query, max_results=3, search_depth="basic"):
        self.calls.append(query)
        base = len(self.calls) * 10
        return {"results": [{"title": f"T{base+i}", "url": f"https://site{base+i}.example/a", "content": f"content {base+i}"} for i in range(self.n)]}


def _script_chat_json(monkeypatch, replies):
    """replies: list of (parsed, status) returned in call order."""
    it = iter(replies)
    monkeypatch.setattr(investigator, "chat_json", lambda **kw: (*next(it)[:1], "", next(iter([None])) or "model") if False else _next(it))


def _next(it):
    parsed, status = next(it)
    return parsed, "", status


EXTRACTION = {
    "event": "Fab shutdown in Taiwan", "impacted_country": "Taiwan", "impacted_category": "Semiconductors",
    "severity": "high", "estimated_duration_days": "14 days",
    "claims": [
        {"claim_id": "C1", "text": "Restart in two days", "type": "duration", "value": "2 days", "source_ids": ["S1"]},
        {"claim_id": "C2", "text": "Restart takes four weeks", "type": "duration", "value": "4 weeks", "source_ids": ["S2", "S99"]},
    ],
}
CONFLICT = {"conflicts": [{"claim_a_id": "C1", "claim_b_id": "C2", "topic": "duration", "explanation": "2 days vs 4 weeks"},
                          {"claim_a_id": "C1", "claim_b_id": "NOPE", "topic": "scope", "explanation": "bad id"}]}


def test_contradiction_resolved_only_with_valid_cited_source(monkeypatch):
    monkeypatch.setattr(investigator, "tavily_client", FakeTavily())
    # follow-up sources get ids S10+ ; cite a valid one
    replies = [(EXTRACTION, "model"), (CONFLICT, "model"), ({"verdict": "claim_b", "evidence_source_ids": ["S10"], "reason": "official notice"}, "model")]
    it = iter(replies)
    monkeypatch.setattr(investigator, "chat_json", lambda **kw: (lambda r: (r[0], "", r[1]))(next(it)))
    rep = investigator.run_investigation("Taiwan fab")
    assert rep.impacted_category == "semiconductor"          # normalized from 'Semiconductors'
    assert rep.estimated_duration_days == 14                   # '14 days' coerced
    assert [s for c in rep.claims for s in c.source_ids if s == "S99"] == []  # invalid source id dropped
    assert len(rep.contradictions) == 1                        # invented claim id ignored
    c = rep.contradictions[0]
    assert c.resolution_status == "resolved" and c.winning_claim_id == "C2" and c.follow_up_source_ids == ["S10"]


def test_contradiction_stays_unresolved_when_judge_is_inconclusive_or_uncited(monkeypatch):
    monkeypatch.setattr(investigator, "tavily_client", FakeTavily())
    replies = [(EXTRACTION, "model"), (CONFLICT, "model"), ({"verdict": "claim_a", "evidence_source_ids": ["S1"], "reason": "x"}, "model")]
    it = iter(replies)
    monkeypatch.setattr(investigator, "chat_json", lambda **kw: (lambda r: (r[0], "", r[1]))(next(it)))
    rep = investigator.run_investigation("Taiwan fab")
    assert rep.contradictions[0].resolution_status == "unresolved"   # cited S1 is not a follow-up source
    assert rep.confidence < 0.83


def test_model_failure_never_fabricates_an_event(monkeypatch):
    monkeypatch.setattr(investigator, "tavily_client", FakeTavily())
    monkeypatch.setattr(investigator, "chat_json", lambda **kw: (None, "", "degraded"))
    rep = investigator.run_investigation("Iceland volcano ash closes airspace")
    assert rep.extraction_method == "degraded"
    assert rep.impacted_country is None and rep.impacted_category is None
    assert rep.severity == "unknown"


def test_no_sources_is_degraded_not_invented(monkeypatch):
    monkeypatch.setattr(investigator, "tavily_client", FakeTavily(n=0))
    monkeypatch.setattr(investigator, "chat_json", lambda **kw: (_ for _ in ()).throw(AssertionError("model must not be called without sources")))
    rep = investigator.run_investigation("anything")
    assert rep.extraction_method == "degraded" and rep.impacted_country is None


# ---------------------------------------------------------------- strategist
def test_strategist_repairs_plant_material_and_drops_unapproved_supplier(monkeypatch):
    exp = _exposure()
    alt = _first_alt(exp)
    po = next(p for p in exp["affected_open_pos"] if p["po_id"] == alt["po_id"])
    model_reply = {
        "headline": "H", "criticality_summary": "S",
        "recommended_actions": [
            {"priority": 1, "title": "good", "action_type": "reroute_supplier", "po_id": alt["po_id"], "target_supplier_id": alt["alt_supplier_id"], "rationale": "r"},
            {"priority": 2, "title": "bad supplier", "action_type": "reroute_supplier", "po_id": exp["affected_open_pos"][1]["po_id"], "target_supplier_id": "SUP-NOPE", "rationale": "r"},
            {"priority": 3, "title": "ghost po", "action_type": "reroute_supplier", "po_id": "PO-GHOST", "target_supplier_id": alt["alt_supplier_id"], "rationale": "r"},
        ],
    }
    monkeypatch.setattr(strategist, "chat_json", lambda **kw: (model_reply, "", "model"))
    brief = strategist.generate_mitigation_strategy({"impacted_country": "Taiwan"}, exp, model_id="m")
    assert brief.brief_source == "nemotron" and brief.model_used == "m"
    assert [a.po_id for a in brief.recommended_actions] == [alt["po_id"]]
    a = brief.recommended_actions[0]
    assert a.target_plant == po["plant_name"] and a.target_material == po["material_id"]
    assert a.value_rerouted_eur == pytest.approx(po["value_eur"])
    assert brief.financial_risk_eur == pytest.approx(exp["total_exposure_eur"])


def test_strategist_fallback_is_internally_consistent_and_labelled(monkeypatch):
    exp = _exposure()
    monkeypatch.setattr(strategist, "chat_json", lambda **kw: (None, "", "degraded"))
    brief = strategist.generate_mitigation_strategy({"impacted_country": "Taiwan"}, exp, model_id="m")
    assert brief.brief_source == "deterministic_fallback" and brief.model_used is None
    assert brief.recommended_actions
    checks = run_deterministic_checks(brief.model_dump(), exp)
    assert all(c.passed for c in checks if c.id != "brief_generated_by_model")


def test_strategist_does_not_invent_runway():
    exp = {"matched": True, "total_exposure_eur": 10.0, "open_pos_count": 1, "critical_runway_days": None,
           "affected_open_pos": [], "mitigation_alternatives": []}
    import types
    strategist.chat_json, orig = (lambda **kw: (None, "", "degraded")), strategist.chat_json
    try:
        brief = strategist.generate_mitigation_strategy({}, exp, model_id="m")
    finally:
        strategist.chat_json = orig
    assert brief.assembly_line_deadline_days is None


# ---------------------------------------------------------------- critic
def test_critic_flags_tampered_numbers_and_mismatched_plant(monkeypatch):
    exp = _exposure()
    alt = _first_alt(exp)
    po = next(p for p in exp["affected_open_pos"] if p["po_id"] == alt["po_id"])
    brief = {"headline": "x", "financial_risk_eur": 1.0, "assembly_line_deadline_days": 99.0, "brief_source": "nemotron",
             "recommended_actions": [{"priority": 1, "po_id": alt["po_id"], "action_type": "reroute_supplier",
                                      "target_supplier_id": "SUP-NOPE", "target_plant": "Atlantis", "target_material": po["material_id"]}]}
    failed = {c.id for c in run_deterministic_checks(brief, exp) if not c.passed}
    assert {"total_matches_sql", "deadline_matches_runway", "suppliers_are_erp_approved", "plant_material_match_po"} <= failed
    monkeypatch.setattr("critic.chat_json", lambda **kw: ({"challenges": [], "verdict": "accept"}, "", "model"))
    report = critique_and_verify(brief, exp, [], [], client=None, model_id="m")
    assert report.verdict == "revise"   # a failed deterministic check always forces revise


def test_critic_verdict_is_unverified_when_model_unavailable(monkeypatch):
    exp = _exposure()
    brief = strategist.generate_mitigation_strategy({}, exp, model_id="m")  # real chat_json fails offline -> fallback brief
    monkeypatch.setattr("critic.chat_json", lambda **kw: (None, "", "degraded"))
    report = critique_and_verify(brief.model_dump(), exp, [], [], client=None, model_id="m")
    assert report.status == "degraded" and report.verdict == "unverified" and report.model_used is None


def test_critic_can_accept_a_sound_plan(monkeypatch):
    exp = _exposure()
    pos = {p["po_id"]: p for p in exp["affected_open_pos"]}
    # one reroute per distinct alternative supplier so no concentration finding fires
    acts = strategist.deterministic_actions(exp, limit=3)
    brief = strategist.ExecutiveBrief(headline="h", criticality_summary="s", financial_risk_eur=exp["total_exposure_eur"],
                                      assembly_line_deadline_days=exp["critical_runway_days"], recommended_actions=acts[:1],
                                      brief_source="nemotron", model_used="m").model_dump()
    monkeypatch.setattr("critic.chat_json", lambda **kw: ({"challenges": [], "verdict": "accept"}, "", "model"))
    report = critique_and_verify(brief, exp, [], [], client=None, model_id="m")
    assert not [c for c in report.checks if not c.passed]
    assert report.verdict in ("accept", "revise")  # concentration (single action) is advisory, never a fake score
    assert not hasattr(report, "score")


# ---------------------------------------------------------------- API
def _stub_pipeline(monkeypatch, degraded=False):
    class Rep:
        pass

    def fake_investigation(query, model_id=None, on_progress=None):
        on_progress and on_progress("research", "searching")
        on_progress and on_progress("extraction", "extracting")
        return investigator.IntelligenceReport(
            event="e", impacted_country=None if degraded else "Taiwan", impacted_category=None if degraded else "semiconductor",
            severity="high", confidence=0.7, sources=[], claims=[], contradictions=[], evidence_strength="70%", search_log=[],
            extraction_method="degraded" if degraded else "model")
    monkeypatch.setattr(api, "run_investigation", fake_investigation)
    monkeypatch.setattr(api, "resolve_nemotron_model", lambda: "nano-x")
    monkeypatch.setattr(api, "resolve_super_model", lambda: "super-x")
    monkeypatch.setattr(strategist, "chat_json", lambda **kw: (None, "", "degraded"))
    monkeypatch.setattr("critic.chat_json", lambda **kw: ({"challenges": [], "verdict": "accept"}, "", "model"))


def test_scan_reports_real_models_and_degraded_stages(monkeypatch):
    _stub_pipeline(monkeypatch)
    r = client.post("/api/disruption/scan", json={"query": "Taiwan chips"}).json()
    prov = r["provenance"]
    assert prov["models"]["extraction"] == "nano-x"
    assert prov["models"]["strategy"] is None            # strategist fell back, so no model is claimed
    assert prov["models"]["critic"] == "super-x"
    assert "strategy" in prov["degraded"]
    assert r["brief"]["brief_source"] == "deterministic_fallback"


def test_scan_without_interpretation_reports_no_exposure(monkeypatch):
    _stub_pipeline(monkeypatch, degraded=True)
    r = client.post("/api/disruption/scan", json={"query": "Brazil coffee harvest"}).json()
    assert r["matched"] is False and r["brief"] is None and "extraction" in r["provenance"]["degraded"]
    assert r["exposure"]["total_exposure_eur"] == 0.0


def test_stream_emits_real_stages_then_result(monkeypatch):
    _stub_pipeline(monkeypatch)
    with client.stream("GET", "/api/disruption/scan/stream", params={"query": "Taiwan chips"}) as resp:
        events = [json.loads(line[6:]) for line in resp.iter_lines() if line.startswith("data: ")]
    stages = [e["stage"] for e in events]
    assert stages[-1] == "result" and events[-1]["data"]["matched"] is True
    for s in ("research", "extraction", "exposure", "strategy", "critic"):
        assert s in stages
    assert stages.index("research") < stages.index("extraction") < stages.index("exposure") < stages.index("strategy") < stages.index("critic")


def test_stream_reports_errors_instead_of_hanging(monkeypatch):
    monkeypatch.setattr(api, "resolve_nemotron_model", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    with client.stream("GET", "/api/disruption/scan/stream", params={"query": "x"}) as resp:
        events = [json.loads(line[6:]) for line in resp.iter_lines() if line.startswith("data: ")]
    assert events[-1]["stage"] == "error" and "boom" in events[-1]["message"]


def test_execute_validates_each_po_and_rejects_unapproved_suppliers(fresh_db):
    exp = _exposure()
    alt = _first_alt(exp)
    bad = client.post("/api/mitigation/execute", json={"actions": [{"po_id": alt["po_id"], "alt_supplier_id": "SUP-NOPE"}]})
    assert bad.status_code == 409
    ok = client.post("/api/mitigation/execute", json={
        "actions": [{"po_id": alt["po_id"], "alt_supplier_id": alt["alt_supplier_id"]}],
        "target_country": "Taiwan", "target_category": "semiconductor"})
    assert ok.status_code == 200
    body = ok.json()
    assert body["execution"]["rerouted_pos_count"] == 1
    assert body["updated_exposure"]["open_pos_count"] == exp["open_pos_count"] - 1
    again = client.post("/api/mitigation/execute", json={"actions": [{"po_id": alt["po_id"], "alt_supplier_id": alt["alt_supplier_id"]}]})
    assert again.status_code == 409                       # cannot reroute the same PO twice


def test_legacy_batch_execute_cannot_bypass_validation(fresh_db):
    exp = _exposure()
    ids = [p["po_id"] for p in exp["affected_open_pos"]]
    r = client.post("/api/mitigation/execute", json={"po_ids": ids, "alt_supplier_id": "SUP014",
                                                      "target_country": "Taiwan", "target_category": "semiconductor"})
    body = r.json()
    ok = body["execution"]["rerouted_pos_count"] if r.status_code == 200 else 0
    assert ok < len(ids)                                  # POs where SUP014 is not approved are refused


def test_revise_returns_real_audit_not_a_canned_verdict(monkeypatch, fresh_db):
    exp = _exposure()
    alt = _first_alt(exp)
    monkeypatch.setattr(api, "resolve_super_model", lambda: "super-x")
    reply = {"headline": "H2", "criticality_summary": "S2", "recommended_actions": [
        {"priority": 1, "title": "t", "action_type": "reroute_supplier", "po_id": alt["po_id"], "target_supplier_id": alt["alt_supplier_id"], "rationale": "r"}]}
    monkeypatch.setattr(strategist, "chat_json", lambda **kw: (reply, "", "model"))
    monkeypatch.setattr("critic.chat_json", lambda **kw: ({"challenges": [{"target": "Action 1", "issue_type": "unsupported_assumption",
                                                                          "severity": "high", "explanation": "capacity unknown", "suggested_fix": "confirm"}],
                                                           "verdict": "revise"}, "", "model"))
    r = client.post("/api/mitigation/revise", json={
        "brief": {}, "critique": {"verdict": "revise", "challenges": []},
        "intelligence": {"impacted_country": "Taiwan", "impacted_category": "semiconductor", "claims": [], "contradictions": []}})
    assert r.status_code == 200
    body = r.json()
    assert body["critique"]["verdict"] == "revise"        # the critic was actually re-run and may still object
    assert body["critique"]["revised"] is True and body["previous_verdict"] == "revise"


def test_revise_refuses_when_model_unavailable(monkeypatch, fresh_db):
    monkeypatch.setattr(api, "resolve_super_model", lambda: "super-x")
    monkeypatch.setattr(strategist, "chat_json", lambda **kw: (None, "", "degraded"))
    r = client.post("/api/mitigation/revise", json={
        "brief": {}, "critique": {"challenges": []},
        "intelligence": {"impacted_country": "Taiwan", "impacted_category": "semiconductor"}})
    assert r.status_code == 502


def test_cached_scenarios_are_upgraded_with_checks():
    r = client.get("/api/cache/scenario/taiwan_semiconductor")
    assert r.status_code == 200
    body = r.json()
    assert body["cached"] is True and body["recorded_at"]
    assert body["critique"]["checks"]
    live = evaluate_erp_exposure("Taiwan", "semiconductor")
    assert body["exposure"]["total_exposure_eur"] == live["total_exposure_eur"]          # recomputed, never stale
    failed = [c for c in body["critique"]["checks"] if not c["passed"] and c["id"] != "brief_generated_by_model"]
    assert not failed                                                                   # served plan agrees with the ERP
    assert client.get("/api/cache/scenario/..%2Fsecret").status_code == 404


def test_rate_limit(monkeypatch):
    _stub_pipeline(monkeypatch)
    monkeypatch.setenv("SCAN_RATE_LIMIT", "2")
    api._rate_hits.clear()
    codes = [client.post("/api/disruption/scan", json={"query": "q"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    api._rate_hits.clear()


def test_health_has_no_secrets():
    body = client.get("/api/health").json()
    assert set(body["keys"]) == {"nebius", "tavily"} and all(isinstance(v, bool) for v in body["keys"].values())


def test_whatif_counts_each_po_once_even_with_two_alternatives():
    r = simulate_whatif("Japan", "sensor", 28, 100.0, True)   # two approved alternatives per PO
    ids = [p["po_id"] for p in r["pos"]]
    assert len(ids) == len(set(ids)) == evaluate_erp_exposure("Japan", "sensor")["open_pos_count"]
    assert r["totals"]["baseline"]["value_at_risk_eur"] == pytest.approx(
        sum(p["baseline"]["value_at_risk_eur"] for p in r["pos"]), abs=1.0)


@pytest.mark.parametrize("country,category", [("Taiwan", "semiconductor"), ("Poland", "battery component"),
                                              ("Germany", "battery component"), ("Japan", "sensor")])
def test_every_demo_scenario_has_approved_alternatives_after_reset(fresh_db, country, category):
    exposure = evaluate_erp_exposure(country, category)
    assert exposure["matched"] and all(p["has_alternative"] for p in exposure["affected_open_pos"])


# ---------------------------------------------------------------- placeholder echo / normalization
def test_normalizer_returns_only_database_values():
    from normalizer import get_db_vocabulary, normalize_category, normalize_country
    countries, categories = get_db_vocabulary()
    for junk in ["Country name (e.g. Taiwan, Poland, Japan) or null", "null", "Brazil", "Poland and Germany", "", None]:
        assert normalize_country(junk, countries) is None
    for junk in ["semiconductor | battery component | sensor | null", "automotive", "coffee", None]:
        assert normalize_category(junk, categories) is None
    assert normalize_country("Taiwan, China", countries) == "Taiwan"
    assert normalize_country("Republic of Korea", countries) == "South Korea"
    assert normalize_category("Battery Cells", categories) == "battery component"
    assert normalize_category("Semiconductors", categories) == "semiconductor"


PLACEHOLDER_ECHO = {
    "event": "Battery plant outage", "impacted_country": "Country name (e.g. Taiwan, Poland, Japan) or null",
    "impacted_category": "semiconductor | battery component | sensor | null", "severity": "high",
    "estimated_duration_days": None, "claims": [],
}


def _run_with_model_reply(monkeypatch, query, reply):
    monkeypatch.setattr(investigator, "tavily_client", FakeTavily())
    seen = {}

    def fake(**kw):
        seen.setdefault("prompt", kw["system_prompt"])
        return (reply, "", "model")
    monkeypatch.setattr(investigator, "chat_json", fake)
    return investigator.run_investigation(query), seen


def test_placeholder_echo_recovers_from_the_users_own_query_and_says_so(monkeypatch):
    rep, _ = _run_with_model_reply(monkeypatch, "Poland battery cell plant production disruption EV supply", PLACEHOLDER_ECHO)
    assert (rep.impacted_country, rep.impacted_category) == ("Poland", "battery component")
    assert rep.mapping_source == "query_text"
    assert evaluate_erp_exposure(rep.impacted_country, rep.impacted_category)["matched"]


def test_placeholder_echo_with_nothing_to_recover_means_no_exposure(monkeypatch):
    rep, _ = _run_with_model_reply(monkeypatch, "Brazil coffee harvest failure", {**PLACEHOLDER_ECHO, "event": "Coffee harvest failure"})
    assert rep.impacted_country is None and rep.impacted_category is None


def test_extraction_prompt_lists_real_vocabulary_and_has_no_copyable_placeholders(monkeypatch):
    _, seen = _run_with_model_reply(monkeypatch, "Taiwan fab shutdown", PLACEHOLDER_ECHO)
    prompt = seen["prompt"]
    for name in ("Poland", "South Korea", "semiconductor", "battery component", "sensor"):
        assert name in prompt
    assert "e.g. Taiwan, Poland, Japan" not in prompt and "| battery component |" not in prompt
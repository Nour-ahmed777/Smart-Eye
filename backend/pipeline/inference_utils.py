from backend.pipeline.analyzer import merge_results
from backend.pipeline.rule_engine import evaluate_rules
from backend.pipeline.zone_filter import filter_detections_by_zone


def build_state(detection_results, camera_id, frame_w, frame_h):
    zone_results = filter_detections_by_zone(detection_results, camera_id, frame_w, frame_h)
    all_triggered = []
    seen_rule_ids = set()
    primary = None
    for zr in zone_results:
        state = merge_results(zr["results"], camera_id, zr["zone"])
        if primary is None:
            primary = state
        for rule in evaluate_rules(state, camera_id):
            rid = rule.get("id")
            if rid in seen_rule_ids:
                continue
            seen_rule_ids.add(rid)
            all_triggered.append(rule)
    if primary is None:
        primary = merge_results(detection_results, camera_id)
    return primary, all_triggered

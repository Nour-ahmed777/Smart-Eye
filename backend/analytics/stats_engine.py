from backend.repository import db


def get_summary(date_from=None, date_to=None, camera_id=None, min_alarm_level=None):
    stats = db.get_detection_stats(date_from, date_to, camera_id, min_alarm_level=min_alarm_level)
    total = stats.get("total", 0) or 0
    violations = stats.get("violations", 0) or 0
    compliant = total - violations
    rate = (compliant / total * 100) if total > 0 else 100.0
    return {
        "total_detections": total,
        "violations": violations,
        "compliant": compliant,
        "compliance_rate": round(rate, 1),
    }


def get_compliance_trend(rule_name=None, date_from=None, date_to=None, camera_id=None, time_basis=None):
    rows = db.get_compliance_over_time(rule_name, date_from, date_to, camera_id=camera_id, time_basis=time_basis)
    trend = []
    for row in rows:
        total = row.get("total", 0) or 0
        compliant = row.get("compliant", 0) or 0
        rate = (compliant / total * 100) if total > 0 else 100.0
        trend.append(
            {
                "date": row["day"],
                "total": total,
                "compliant": compliant,
                "rate": round(rate, 1),
            }
        )
    return trend


def get_hourly_violation_chart(date_from=None, date_to=None, camera_id=None, rule_name=None, min_alarm_level=None, time_basis=None):
    rows = db.get_hourly_violations(
        date_from, date_to, camera_id=camera_id, rule_name=rule_name, min_alarm_level=min_alarm_level, time_basis=time_basis
    )
    hours = {str(i).zfill(2): 0 for i in range(24)}
    for row in rows:
        hours[row["hour"]] = row["count"]
    return [{"hour": h, "count": c} for h, c in sorted(hours.items())]


def get_person_violations(date_from=None, date_to=None, camera_id=None, rule_name=None, min_alarm_level=None, limit=20):
    return db.get_violations_by_person(
        date_from, date_to, camera_id=camera_id, rule_name=rule_name, min_alarm_level=min_alarm_level, limit=limit
    )


def get_camera_activity_data(date_from=None, date_to=None, camera_id=None):
    return db.get_camera_activity(date_from, date_to, camera_id=camera_id)


def get_identified_count(date_from=None, date_to=None, camera_id=None, rule_name=None, min_alarm_level=None):
    res = db.get_identified_count(date_from, date_to, camera_id=camera_id, rule_name=rule_name, min_alarm_level=min_alarm_level)
    return res.get("count", 0) if isinstance(res, dict) else 0

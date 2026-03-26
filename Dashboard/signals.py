def action_from_signal(signal: str) -> str:
    if signal == '🔵 BLUE':
        return 'Watch Closely'
    if signal == '🟢 GREEN':
        return 'Buy Zone'
    if signal == '🟡 YELLOW':
        return 'Wait'
    return 'Avoid For Now'


def signal_and_reason(day_pct: float, week_pct: float, month_pct: float, volume_ratio: float) -> tuple[str, str]:
    reasons = []

    if day_pct >= 6:
        reasons.append('strong daily move')
    if week_pct >= 10:
        reasons.append('strong weekly trend')
    if month_pct >= 15:
        reasons.append('good monthly strength')
    if volume_ratio >= 2:
        reasons.append('heavy volume')
    if day_pct > 0:
        reasons.append('buyers in control')

    if day_pct >= 6 and week_pct >= 10 and volume_ratio >= 2:
        return '🔵 BLUE', ', '.join(reasons[:3]) or 'explosive setup'
    if day_pct >= 2 or (week_pct >= 5 and volume_ratio >= 1.2):
        return '🟢 GREEN', ', '.join(reasons[:3]) or 'positive setup'
    if day_pct > -2:
        return '🟡 YELLOW', ', '.join(reasons[:3]) or 'mixed setup'
    return '🔴 RED', 'weak price action'

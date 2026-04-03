def classify_setup(day_pct, week_pct, month_pct, volume_ratio, current_price, high_52):
    explosive = False
    smart_money = False
    breakout_watch = False

    near_high = False
    if high_52 and high_52 > 0:
        near_high = current_price >= high_52 * 0.90

    if day_pct >= 3 and week_pct >= 5 and volume_ratio >= 1.3:
        explosive = True

    if volume_ratio >= 1.4 and month_pct >= 5:
        smart_money = True

    if near_high and week_pct >= 3 and volume_ratio >= 1.2:
        breakout_watch = True

    return explosive, smart_money, breakout_watch


def score_stock(day_pct, week_pct, month_pct, volume_ratio, current_price, high_52, signal):
    score = 0

    score += max(day_pct, 0) * 1.5
    score += max(week_pct, 0) * 1.2
    score += max(month_pct, 0) * 0.8
    score += min(volume_ratio, 3) * 8

    if high_52 and high_52 > 0:
        distance_from_high = (current_price / high_52) * 100
        if distance_from_high >= 95:
            score += 12
        elif distance_from_high >= 90:
            score += 8
        elif distance_from_high >= 85:
            score += 4

    if signal == "🔵 BLUE":
        score += 20
    elif signal == "🟢 GREEN":
        score += 12
    elif signal == "🟡 YELLOW":
        score += 4

    return round(score, 2)


def scanner_label(explosive, smart_money, breakout_watch):
    labels = []

    if explosive:
        labels.append("Explosive")
    if smart_money:
        labels.append("Smart Money")
    if breakout_watch:
        labels.append("Breakout Watch")

    if not labels:
        return "Normal"

<<<<<<< HEAD
    return " | ".join(labels)
=======
    return " | ".join(labels)
>>>>>>> a2263f5 (Added signup route)

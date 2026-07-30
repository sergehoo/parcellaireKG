"""Tests Phase 1 : planification (compute_next_send_at) + sévérité."""
from datetime import date, datetime, time

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from alerting.models import (
    AlertConfiguration, AlertThreshold, Frequency, Severity,
)


def aw(y, m, d, hh=0, mm=0):
    dt = datetime(y, m, d, hh, mm)
    if settings.USE_TZ:
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


class NextSendAtTests(TestCase):
    def test_manual_returns_none(self):
        cfg = AlertConfiguration(frequency=Frequency.MANUAL)
        self.assertIsNone(cfg.compute_next_send_at(aw(2026, 7, 15)))

    def test_weekly_next_monday(self):
        cfg = AlertConfiguration(frequency=Frequency.WEEKLY, day_of_week=0, send_time=time(8, 0))
        after = aw(2026, 7, 15, 10, 0)  # un jour de semaine à 10h
        nxt = cfg.compute_next_send_at(after)
        self.assertEqual(nxt.weekday(), 0)      # lundi
        self.assertGreater(nxt, after)
        self.assertEqual(nxt.hour, 8)

    def test_weekly_same_day_before_time(self):
        # day_of_week = aujourd'hui, mais l'heure d'envoi n'est pas passée → aujourd'hui.
        after = aw(2026, 7, 13, 6, 0)  # 2026-07-13 est un lundi ; 6h < 8h
        cfg = AlertConfiguration(frequency=Frequency.WEEKLY, day_of_week=0, send_time=time(8, 0))
        nxt = cfg.compute_next_send_at(after)
        self.assertEqual(nxt.date(), date(2026, 7, 13))

    def test_weekly_same_day_after_time_rolls_a_week(self):
        after = aw(2026, 7, 13, 9, 0)  # lundi 9h > 8h → lundi suivant
        cfg = AlertConfiguration(frequency=Frequency.WEEKLY, day_of_week=0, send_time=time(8, 0))
        nxt = cfg.compute_next_send_at(after)
        self.assertEqual(nxt.date(), date(2026, 7, 20))

    def test_biweekly_steps_14_days_from_start(self):
        cfg = AlertConfiguration(frequency=Frequency.BIWEEKLY,
                                 start_date=date(2026, 7, 1), send_time=time(8, 0))
        nxt = cfg.compute_next_send_at(aw(2026, 7, 10))
        self.assertEqual(nxt.date(), date(2026, 7, 15))

    def test_monthly_last_day_clamped(self):
        # day_of_month=31 en avril (30 jours) → 30 avril.
        cfg = AlertConfiguration(frequency=Frequency.MONTHLY, day_of_month=31, send_time=time(8, 0))
        nxt = cfg.compute_next_send_at(aw(2026, 4, 10))
        self.assertEqual(nxt.date(), date(2026, 4, 30))

    def test_monthly_rolls_to_next_month_when_past(self):
        cfg = AlertConfiguration(frequency=Frequency.MONTHLY, day_of_month=5, send_time=time(8, 0))
        nxt = cfg.compute_next_send_at(aw(2026, 4, 10))  # le 5 est passé
        self.assertEqual(nxt.date(), date(2026, 5, 5))

    def test_custom_interval_from_last_sent(self):
        cfg = AlertConfiguration(frequency=Frequency.CUSTOM, custom_interval_days=10,
                                 last_sent_at=aw(2026, 7, 1, 8, 0), send_time=time(8, 0))
        nxt = cfg.compute_next_send_at(aw(2026, 7, 5))
        self.assertEqual(nxt.date(), date(2026, 7, 11))

    def test_skip_weekends_rolls_to_monday(self):
        cfg = AlertConfiguration(frequency=Frequency.WEEKLY, day_of_week=5,  # samedi
                                 skip_weekends=True, send_time=time(8, 0))
        nxt = cfg.compute_next_send_at(aw(2026, 7, 15, 10, 0))
        self.assertEqual(nxt.weekday(), 0)  # reporté au lundi

    def test_end_date_returns_none(self):
        cfg = AlertConfiguration(frequency=Frequency.WEEKLY, day_of_week=0,
                                 end_date=date(2026, 7, 1))
        self.assertIsNone(cfg.compute_next_send_at(aw(2026, 7, 15)))

    def test_excluded_date_is_skipped(self):
        cfg = AlertConfiguration(frequency=Frequency.MONTHLY, day_of_month=5, send_time=time(8, 0),
                                 excluded_dates=["2026-05-05"])
        nxt = cfg.compute_next_send_at(aw(2026, 4, 10))  # viserait le 5 mai, exclu → 6 mai
        self.assertEqual(nxt.date(), date(2026, 5, 6))


class SeverityThresholdTests(TestCase):
    def test_default_thresholds_classify(self):
        th = AlertThreshold()  # défauts 10 / 25 / 40
        self.assertEqual(th.classify(5), Severity.INFORMATION)
        self.assertEqual(th.classify(10), Severity.VIGILANCE)
        self.assertEqual(th.classify(24.9), Severity.VIGILANCE)
        self.assertEqual(th.classify(25), Severity.IMPORTANT)
        self.assertEqual(th.classify(40), Severity.CRITICAL)
        self.assertEqual(th.classify(62), Severity.CRITICAL)
        self.assertEqual(th.classify(None), Severity.INFORMATION)

    def test_custom_thresholds(self):
        th = AlertThreshold(vigilance_min=5, important_min=15, critical_min=30)
        self.assertEqual(th.classify(6), Severity.VIGILANCE)
        self.assertEqual(th.classify(20), Severity.IMPORTANT)
        self.assertEqual(th.classify(35), Severity.CRITICAL)

    def test_refresh_next_send_at_persists(self):
        cfg = AlertConfiguration.objects.create(
            name="Hebdo DG", frequency=Frequency.WEEKLY, day_of_week=0)
        cfg.refresh_next_send_at()
        cfg.refresh_from_db()
        self.assertIsNotNone(cfg.next_send_at)
        self.assertEqual(cfg.next_send_at.weekday(), 0)

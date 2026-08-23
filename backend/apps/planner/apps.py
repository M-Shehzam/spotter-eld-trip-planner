import os

from django.apps import AppConfig


class PlannerConfig(AppConfig):
    name = "apps.planner"
    label = "planner"
    verbose_name = "Trip planner"

    def ready(self) -> None:
        """Optionally load the gazetteer at start-up.

        Off by default, because ``ready`` also runs for migrations, shell
        sessions and the test suite. The deployed service sets
        WARM_INDEX_ON_START so the first driver to plan a trip does not pay
        the third of a second of CSV parsing.
        """
        if os.getenv("WARM_INDEX_ON_START", "").strip().lower() not in {"1", "true", "yes"}:
            return

        try:
            from apps.planner.places import get_index

            get_index()
        except Exception:  # pragma: no cover - start-up must never die here
            import logging

            logging.getLogger(__name__).warning("Place index warm-up skipped", exc_info=True)

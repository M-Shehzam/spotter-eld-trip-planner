from django.urls import path

from apps.planner import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("places/suggest/", views.suggest_places, name="place-suggestions"),
    path("trips/", views.plan_trip, name="plan-trip"),
    path("trips/<uuid:trip_id>/", views.retrieve_trip, name="retrieve-trip"),
]

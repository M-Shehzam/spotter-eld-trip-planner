import type { PlaceSuggestion, Trip, TripRequest } from "../types/trip";

import { api } from "./client";

export function planTrip(request: TripRequest, onSlow?: () => void): Promise<Trip> {
  return api.post<Trip>("/api/v1/trips/", request, { onSlow });
}

export function getTrip(id: string, onSlow?: () => void): Promise<Trip> {
  return api.get<Trip>(`/api/v1/trips/${id}/`, { onSlow });
}

export function suggestPlaces(
  query: string,
  signal?: AbortSignal,
): Promise<PlaceSuggestion[]> {
  return api
    .get<{ results: PlaceSuggestion[] }>(
      `/api/v1/places/suggest/?q=${encodeURIComponent(query)}&limit=8`,
      { signal },
    )
    .then((body) => body.results);
}

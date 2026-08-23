import { useEffect, useRef, useState } from "react";

import { suggestPlaces } from "../api/trips";
import type { PlaceSuggestion } from "../types/trip";

/**
 * Completions for a location field.
 *
 * Debounced at 160ms, which is short enough that the list feels attached to
 * the keyboard and long enough that a fast typist does not fire eight
 * requests crossing a city name. Each new query aborts the one before it, so
 * a slow response can never overwrite a newer one.
 */
export function usePlaceSuggestions(query: string) {
  const [options, setOptions] = useState<PlaceSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const inFlight = useRef<AbortController | null>(null);

  useEffect(() => {
    const trimmed = query.trim();

    if (trimmed.length < 2) {
      setOptions([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    const timer = setTimeout(() => {
      inFlight.current?.abort();
      const controller = new AbortController();
      inFlight.current = controller;

      suggestPlaces(trimmed, controller.signal)
        .then((results) => {
          if (!controller.signal.aborted) setOptions(results);
        })
        .catch(() => {
          // A failed lookup should never block typing; the field still
          // accepts free text and the server resolves it on submit.
          if (!controller.signal.aborted) setOptions([]);
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, 160);

    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => () => inFlight.current?.abort(), []);

  return { options, loading };
}

import { useEffect, useState } from "react";
import { api } from "./api/client";

interface Health {
  status: string;
  routing_provider: string;
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<Health>("/api/v1/health/")
      .then(setHealth)
      .catch((cause) => setError(cause.message));
  }, []);

  return (
    <main style={{ fontFamily: "system-ui", padding: "2rem" }}>
      <h1>Spotter ELD Trip Planner</h1>
      <p>Backend: {error ?? health?.status ?? "checking…"}</p>
    </main>
  );
}

/** The shape the planner API returns. Mirrors apps/planner/services.py. */

export type DutyStatus = "off_duty" | "sleeper_berth" | "driving" | "on_duty";

export type StopKind =
  | "start"
  | "drive"
  | "pickup"
  | "dropoff"
  | "fuel"
  | "break"
  | "rest"
  | "restart";

export interface ResolvedLocation {
  label: string;
  latitude: number;
  longitude: number;
  query: string;
  source: "coordinates" | "gazetteer";
}

export interface TripInputs {
  current_location: ResolvedLocation;
  pickup_location: ResolvedLocation;
  dropoff_location: ResolvedLocation;
  current_cycle_used_hours: number;
  start_datetime: string;
  timezone: string;
  driver_name: string;
  carrier_name: string;
  truck_number: string;
}

export interface RouteLeg {
  from: string;
  to: string;
  distance_miles: number;
  drive_hours: number;
  start_mile: number;
  end_mile: number;
}

export interface Route {
  /** [latitude, longitude] pairs, already thinned for drawing. */
  geometry: [number, number][];
  /** [west, south, east, north] */
  bbox: [number, number, number, number];
  distance_miles: number;
  drive_hours: number;
  legs: RouteLeg[];
}

export interface Stop {
  seq: number;
  kind: StopKind;
  title: string;
  location: string;
  latitude: number;
  longitude: number;
  mile_marker: number;
  arrive: string | null;
  depart: string;
  duration_hours: number;
}

export interface Segment {
  status: DutyStatus;
  kind: StopKind;
  start: string;
  end: string;
  hours: number;
  miles: number;
  label: string;
  location: string;
  start_mile: number;
  end_mile: number;
}

export interface GridEntry {
  status: DutyStatus;
  /** 1 off duty, 2 sleeper berth, 3 driving, 4 on duty. */
  row: 1 | 2 | 3 | 4;
  start_hour: number;
  end_hour: number;
  hours: number;
}

export interface LogRemark {
  hour: number;
  text: string;
  location: string;
  kind: StopKind;
}

export interface LogRecap {
  on_duty_today: number;
  on_duty_last_8: number;
  available_tomorrow: number;
  /** Null when the trip is too short for the answer to come from the plan. */
  on_duty_last_7: number | null;
}

export interface LogSheet {
  date: string;
  sheet_number: number;
  of: number;
  from_label: string;
  to_label: string;
  total_miles_driving: number;
  total_mileage: number;
  entries: GridEntry[];
  remarks: LogRemark[];
  totals: Record<DutyStatus, number>;
  recap: LogRecap;
}

export interface TripSummary {
  days: number;
  total_miles: number;
  drive_hours: number;
  on_duty_hours: number;
  off_duty_hours: number;
  sleeper_hours: number;
  elapsed_hours: number;
  departure: string;
  arrival: string;
  average_speed_mph: number;
  fuel_stops: number;
  rest_breaks: number;
  rests: number;
  restarts: number;
  cycle_hours_at_start: number;
  cycle_hours_at_finish: number;
  cycle_hours_available: number;
  compliant: boolean;
  violations: string[];
}

export interface TripMeta {
  provider: string;
  api_calls: number;
  route_fetch_ms: number;
  geometry_points: number;
  truck_speed_factor: number;
  computed_ms: number;
}

export interface Trip {
  id: string;
  created_at: string;
  inputs: TripInputs;
  route: Route;
  stops: Stop[];
  segments: Segment[];
  logs: LogSheet[];
  summary: TripSummary;
  meta: TripMeta;
}

export interface TripRequest {
  current_location: string;
  pickup_location: string;
  dropoff_location: string;
  current_cycle_used_hours: number;
  start_datetime?: string;
  timezone?: string;
  driver_name?: string;
  carrier_name?: string;
  truck_number?: string;
}

export interface PlaceSuggestion {
  label: string;
  name: string;
  state: string;
  latitude: number;
  longitude: number;
  population: number;
}

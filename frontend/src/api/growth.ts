import client from "./client";
import type { ApiEnvelope, GrowthInsight, GrowthPlanItem, GrowthPoint, WeaknessInsight } from "@/types/models";

export function fetchGrowthInsight() {
  return client.get<never, ApiEnvelope<GrowthInsight>>("/growth/insight");
}

export function fetchGrowthTrends() {
  return client.get<never, ApiEnvelope<GrowthPoint[]>>("/growth/trends");
}

export function fetchWeaknesses() {
  return client.get<never, ApiEnvelope<WeaknessInsight[]>>("/growth/weaknesses");
}

export function fetchGrowthPlan() {
  return client.get<never, ApiEnvelope<GrowthPlanItem[]>>("/growth/plan");
}

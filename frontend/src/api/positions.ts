import client from "./client";
import type { ApiEnvelope, JobPosition, PositionDetail } from "@/types/models";

export function fetchPositions() {
  return client.get<never, ApiEnvelope<JobPosition[]>>("/positions");
}

export function fetchPositionDetail(code: string) {
  return client.get<never, ApiEnvelope<PositionDetail>>(`/positions/${code}/competencies`);
}

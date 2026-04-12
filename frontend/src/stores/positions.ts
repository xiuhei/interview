import { defineStore } from "pinia";

import { fetchPositionDetail, fetchPositions } from "@/api/positions";
import type { JobPosition, PositionDetail } from "@/types/models";

export const usePositionStore = defineStore("positions", {
  state: () => ({
    items: [] as JobPosition[],
    detailMap: {} as Record<string, PositionDetail>,
  }),
  actions: {
    async loadPositions() {
      const response = await fetchPositions();
      this.items = response.data;
    },
    async loadDetail(code: string) {
      const response = await fetchPositionDetail(code);
      this.detailMap[code] = response.data;
    },
  },
});

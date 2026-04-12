import * as echarts from "echarts";

import type { GrowthInsight } from "@/types/models";
import { competencyLabel } from "@/utils/display";

export function useGrowthCharts() {
  function renderTrend(element: HTMLDivElement, insight: GrowthInsight) {
    const chart = echarts.init(element);
    chart.setOption({
      backgroundColor: "transparent",
      tooltip: { trigger: "axis" },
      grid: { left: 44, right: 24, top: 32, bottom: 32 },
      xAxis: {
        type: "category",
        data: insight.trends.map((item) => item.date),
        axisLine: { lineStyle: { color: "rgba(91, 107, 123, 0.35)" } },
      },
      yAxis: {
        type: "value",
        min: 0,
        max: 100,
        axisLine: { show: false },
        splitLine: { lineStyle: { color: "rgba(91, 107, 123, 0.12)" } },
      },
      series: [
        {
          type: "line",
          smooth: true,
          data: insight.trends.map((item) => item.total_score),
          symbolSize: 9,
          lineStyle: { width: 3, color: "#5AA9FF" },
          itemStyle: { color: "#7BB8F7" },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: "rgba(90,169,255,0.18)" },
              { offset: 1, color: "rgba(90,169,255,0.02)" },
            ]),
          },
        },
      ],
    });
    return chart;
  }

  function renderCompetency(element: HTMLDivElement, insight: GrowthInsight) {
    const chart = echarts.init(element);
    const progress = [...insight.competency_progress].slice(0, 6).reverse();
    chart.setOption({
      backgroundColor: "transparent",
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      grid: { left: 96, right: 24, top: 24, bottom: 24 },
      xAxis: {
        type: "value",
        min: 0,
        max: 100,
        splitLine: { lineStyle: { color: "rgba(91, 107, 123, 0.12)" } },
      },
      yAxis: {
        type: "category",
        data: progress.map((item) => competencyLabel(item.competency)),
        axisLine: { show: false },
      },
      series: [
        {
          type: "bar",
          data: progress.map((item) => item.average_score),
          barWidth: 18,
          itemStyle: {
            borderRadius: [0, 999, 999, 0],
            color: new echarts.graphic.LinearGradient(1, 0, 0, 0, [
              { offset: 0, color: "#7BB8F7" },
              { offset: 1, color: "#5AA9FF" },
            ]),
          },
        },
      ],
    });
    return chart;
  }

  return { renderTrend, renderCompetency };
}

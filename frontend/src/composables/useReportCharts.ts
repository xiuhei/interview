import * as echarts from "echarts";

import type { InterviewReport } from "@/types/models";

const COMPETENCY_LABELS: Record<string, string> = {
  project_depth: "项目深度",
  frontend_foundation: "前端基础",
  vue_engineering: "Vue 工程化",
  browser_principle: "浏览器原理",
  network_performance: "网络与性能",
  architecture: "架构设计",
  cpp_language: "C++ 语言",
  os_network: "操作系统与网络",
  algorithm: "算法与数据结构",
  system_design: "系统设计",
  performance: "性能优化",
};

function competencyLabel(name: string) {
  return COMPETENCY_LABELS[name] || name;
}

export function useReportCharts() {
  function renderRadar(element: HTMLDivElement, report: InterviewReport) {
    const chart = echarts.init(element);
    chart.setOption({
      backgroundColor: "transparent",
      radar: {
        indicator: report.radar.map((item) => ({ name: competencyLabel(item.name), max: 100 })),
        splitArea: { areaStyle: { color: ["rgba(15,118,110,0.04)", "rgba(201,111,61,0.04)"] } },
      },
      series: [
        {
          type: "radar",
          data: [
            {
              value: report.radar.map((item) => item.value),
              areaStyle: { color: "rgba(15,118,110,0.22)" },
              lineStyle: { color: "#0f766e" },
              itemStyle: { color: "#c96f3d" },
            },
          ],
        },
      ],
    });
    return chart;
  }

  function renderBar(element: HTMLDivElement, report: InterviewReport) {
    const chart = echarts.init(element);
    chart.setOption({
      xAxis: {
        type: "category",
        data: Object.keys(report.competency_scores).map(competencyLabel),
        axisLabel: { rotate: 18 },
      },
      yAxis: { type: "value", max: 100 },
      series: [
        {
          type: "bar",
          data: Object.values(report.competency_scores),
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: "#0f766e" },
              { offset: 1, color: "#c96f3d" },
            ]),
          },
        },
      ],
    });
    return chart;
  }

  return { renderBar, renderRadar };
}

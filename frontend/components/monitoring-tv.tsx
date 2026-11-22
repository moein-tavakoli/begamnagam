"use client";

import { useEffect, useRef, useState } from "react";
import { ManagementMonitoring } from "@/components/management-monitoring";
import { ManagementMonitoringLayout } from "@/components/management-monitoring-layout";

export function MonitoringTv() {
  const viewport = useRef<HTMLDivElement>(null);
  const board = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);

  useEffect(() => {
    const screen = viewport.current;
    const content = board.current;
    if (!screen || !content) return;
    const fit = () => setScale(Math.min(1, screen.clientHeight / Math.max(1, content.scrollHeight)));
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(fit);
    observer?.observe(content);
    window.addEventListener("resize", fit);
    fit();
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", fit);
    };
  }, []);

  return <div ref={viewport} style={{ height: "100vh", overflow: "hidden", background: "#080b18" }}>
    <div ref={board} style={{ transform: `scale(${scale})`, transformOrigin: "top center" }}>
      <ManagementMonitoringLayout active>
        <ManagementMonitoring displayOnly />
      </ManagementMonitoringLayout>
    </div>
  </div>;
}

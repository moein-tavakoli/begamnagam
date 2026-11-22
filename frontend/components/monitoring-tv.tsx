"use client";

import { ManagementMonitoring } from "@/components/management-monitoring";
import { ManagementMonitoringLayout } from "@/components/management-monitoring-layout";

export function MonitoringTv() {
  return (
    <ManagementMonitoringLayout active>
      <ManagementMonitoring displayOnly />
    </ManagementMonitoringLayout>
  );
}

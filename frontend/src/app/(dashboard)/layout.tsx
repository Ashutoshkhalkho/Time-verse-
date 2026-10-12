import React from "react";
import { PortalShell } from "@/components/layout/PortalShell";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <PortalShell>{children}</PortalShell>;
}

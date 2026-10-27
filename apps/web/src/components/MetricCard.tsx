import React from "react";
import { Card, CardContent } from "@/components/ui/card";

interface MetricCardProps {
  title: string;
  value: string | number;
  unit?: string;
  icon?: React.ReactNode;
}

export default function MetricCard({
  title,
  value,
  unit,
  icon,
}: MetricCardProps) {
  return (
    <Card className="h-full">
      <CardContent className="flex items-center justify-between">
        <div>
          <p className="mb-1 text-sm font-bold uppercase text-muted-foreground">
            {title}
          </p>
          <p className="text-3xl font-bold text-primary">
            {value}{" "}
            {unit && (
              <span className="text-lg text-muted-foreground">{unit}</span>
            )}
          </p>
        </div>
        {icon && <div className="text-primary opacity-80">{icon}</div>}
      </CardContent>
    </Card>
  );
}

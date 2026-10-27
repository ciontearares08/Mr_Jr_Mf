import React from "react";
import { Card, CardContent } from "@/components/ui/card";

interface MetricCardProps {
  title: string;
  value: string | number;
  unit?: string;
  // A short line under the value that explains it, e.g. a date range
  description?: string;
  icon?: React.ReactNode;
}

export default function MetricCard({
  title,
  value,
  unit,
  description,
  icon,
}: MetricCardProps) {
  return (
    <Card className="h-full">
      <CardContent className="flex items-start justify-between gap-4">
        <div>
          <p className="mb-2 text-xs font-medium tracking-wide uppercase text-muted-foreground">
            {title}
          </p>
          <p className="text-3xl font-bold">
            {value}{" "}
            {unit && (
              <span className="text-lg font-medium text-muted-foreground">
                {unit}
              </span>
            )}
          </p>
          {description && (
            <p className="mt-1 text-sm text-muted-foreground">{description}</p>
          )}
        </div>

        {/* The icon sits in a small, faintly green square ("badge") */}
        {icon && (
          <div className="rounded-lg bg-primary/10 p-2.5 text-primary">
            {icon}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

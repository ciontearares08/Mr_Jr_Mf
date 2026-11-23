import { Wheat } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { Overview } from "@/services/fieldData";

interface YieldCardProps {
  metric: Overview["metrics"]["predicted_yield"];
}

export default function YieldCard({ metric }: YieldCardProps) {
  const { min, median, max } = metric.value;

  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-center gap-2">
          <div className="rounded-lg bg-primary/10 p-2 text-primary">
            <Wheat className="size-5" />
          </div>
          <CardTitle>Predicted Yield</CardTitle>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div>
          <p className="text-sm text-muted-foreground">Expected yield</p>

          <p className="text-3xl font-bold">
            {median.toFixed(2)}{" "}
            <span className="text-lg font-medium text-muted-foreground">
              {metric.unit}
            </span>
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-lg bg-muted/50 p-3">
            <p className="text-sm text-muted-foreground">Minimum</p>
            <p className="text-lg font-semibold">
              {min.toFixed(2)} {metric.unit}
            </p>
          </div>

          <div className="rounded-lg bg-muted/50 p-3">
            <p className="text-sm text-muted-foreground">Maximum</p>
            <p className="text-lg font-semibold">
              {max.toFixed(2)} {metric.unit}
            </p>
          </div>
        </div>

        <p className="text-xs text-muted-foreground">
          Estimated yield range across simulation runs.
        </p>
      </CardContent>
    </Card>
  );
}
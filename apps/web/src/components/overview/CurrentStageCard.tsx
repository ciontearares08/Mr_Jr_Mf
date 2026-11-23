import { Sprout } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { Overview } from "@/services/fieldData";

interface CurrentStageCardProps {
  current: Overview["stage"]["current"];
  currentSince: Overview["stage"]["current_since"];
}

function formatDate(date: string): string {
  return new Date(`${date}T00:00:00`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export default function CurrentStageCard({
  current,
  currentSince,
}: CurrentStageCardProps) {
  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-center gap-2">
          <div className="rounded-lg bg-primary/10 p-2 text-primary">
            <Sprout className="size-5" />
          </div>
          <CardTitle>Current Stage</CardTitle>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div>
          <p className="text-2xl font-bold">{current.name}</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Growth stage {current.code}
          </p>
        </div>

        <div className="rounded-lg bg-muted/50 p-3">
          <p className="text-sm text-muted-foreground">Zadoks code</p>
          <p className="text-xl font-semibold">{current.zadoks}</p>
        </div>

        <div>
          <p className="text-sm text-muted-foreground">Stage since</p>
          <p className="font-medium">{formatDate(currentSince)}</p>
        </div>
      </CardContent>
    </Card>
  );
}
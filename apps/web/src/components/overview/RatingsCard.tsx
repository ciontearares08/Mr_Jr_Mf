
import { ChartNoAxesColumnIncreasing } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { Overview } from "@/services/fieldData";

interface RatingsCardProps {
  metrics: Overview["metrics"];
}

function RatingIndicator({ rating }: { rating: string }) {
  const styles: Record<string, string> = {
    worst: "bg-red-100 text-red-800",
    poor: "bg-orange-100 text-orange-800",
    fair: "bg-yellow-100 text-yellow-800",
    good: "bg-green-100 text-green-800",
    great: "bg-emerald-100 text-emerald-800",
  };

  return (
    <span
      className={`rounded-full px-3 py-1 text-sm font-medium ${
        styles[rating] ?? "bg-muted text-muted-foreground"
      }`}
    >
      {rating.charAt(0).toUpperCase() + rating.slice(1)}
    </span>
  );
}

export default function RatingsCard({ metrics }: RatingsCardProps) {
  const ratings = [
    {
      name: "Leaf Area Index (LAI)",
      rating: metrics.lai.rating,
      description: "Crop canopy and leaf development",
    },
    {
      name: "Plant Available Water (PAW)",
      rating: metrics.paw.rating,
      description: "Water availability in the root zone",
    },
    {
      name: "Predicted Yield",
      rating: metrics.predicted_yield.rating,
      description: "Assessment of simulated crop production",
    },
  ];

  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-center gap-2">
          <div className="rounded-lg bg-primary/10 p-2 text-primary">
            <ChartNoAxesColumnIncreasing className="size-5" />
          </div>
          <CardTitle>Crop Condition</CardTitle>
        </div>
      </CardHeader>

      <CardContent className="space-y-5">
        {ratings.map((item, index) => (
          <div key={item.name}>
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="font-medium">{item.name}</p>
                <p className="text-sm text-muted-foreground">
                  {item.description}
                </p>
              </div>

              <RatingIndicator rating={item.rating} />
            </div>

            {index < ratings.length - 1 && (
              <div className="mt-5 border-b" />
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

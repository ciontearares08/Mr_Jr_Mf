
import { useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { Overview } from "@/services/fieldData";

interface UpcomingStagesCardProps {
  upcoming: Overview["stage"]["upcoming"];
}

function formatDate(date: string): string {
  return new Date(`${date}T00:00:00`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export default function UpcomingStagesCard({
  upcoming,
}: UpcomingStagesCardProps) {
  const [currentIndex, setCurrentIndex] = useState(0);

  if (upcoming.length === 0) {
    return (
      <Card className="h-full">
        <CardHeader>
          <CardTitle>Upcoming Stages</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            No upcoming stages available.
          </p>
        </CardContent>
      </Card>
    );
  }

  const stage = upcoming[currentIndex];

  const goPrevious = () => {
    setCurrentIndex((index) => Math.max(0, index - 1));
  };

  const goNext = () => {
    setCurrentIndex((index) => Math.min(upcoming.length - 1, index + 1));
  };

  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-center gap-2">
          <div className="rounded-lg bg-primary/10 p-2 text-primary">
            <CalendarDays className="size-5" />
          </div>
          <CardTitle>Upcoming Stages</CardTitle>
        </div>
      </CardHeader>

      <CardContent className="flex flex-col justify-between gap-6">
        <div className="space-y-5">
          <div>
            <p className="text-2xl font-bold">{stage.name}</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Zadoks {stage.zadoks}
            </p>
          </div>

          <div className="rounded-lg bg-muted/50 p-4 space-y-3">
            <div>
              <p className="text-sm text-muted-foreground">
                Expected date
              </p>
              <p className="text-xl font-semibold">
                {formatDate(stage.date.median)}
              </p>
            </div>

            <div className="border-t pt-3">
              <p className="text-sm text-muted-foreground mb-2">
                Estimated date range
              </p>

              <div className="flex justify-between gap-4 text-sm">
                <div>
                  <p className="text-muted-foreground">Earliest</p>
                  <p className="font-medium">
                    {formatDate(stage.date.min)}
                  </p>
                </div>

                <div className="text-right">
                  <p className="text-muted-foreground">Latest</p>
                  <p className="font-medium">
                    {formatDate(stage.date.max)}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-center gap-1.5">
            {upcoming.map((item, index) => (
              <div
                key={item.code}
                className={`h-1.5 rounded-full transition-all ${
                  index === currentIndex
                    ? "w-8 bg-primary"
                    : "w-2 bg-muted"
                }`}
              />
            ))}
          </div>

          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={goPrevious}
              disabled={currentIndex === 0}
              className="inline-flex items-center gap-1 rounded-md border px-3 py-2 text-sm transition-colors hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="size-4" />
              Previous
            </button>

            <span className="text-sm text-muted-foreground">
              {currentIndex + 1} / {upcoming.length}
            </span>

            <button
              type="button"
              onClick={goNext}
              disabled={currentIndex === upcoming.length - 1}
              className="inline-flex items-center gap-1 rounded-md border px-3 py-2 text-sm transition-colors hover:bg-muted disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
              <ChevronRight className="size-4" />
            </button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

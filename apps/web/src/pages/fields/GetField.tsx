import { useEffect, useState } from "react";
import { CircleAlert } from "lucide-react";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";
import type { Overview } from "@/services/fieldData";
import { getOverview } from "@/services/fieldData";
import CurrentStageCard from "@/components/overview/CurrentStageCard";
import UpcomingStagesCard from "@/components/overview/UpcomingStagesCard";
import YieldCard from "@/components/overview/YieldCard";
import RatingsCard from "@/components/overview/RatingsCard";

function formatDate(date: string): string {
  return new Date(`${date}T00:00:00`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export default function GetField() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchOverview() {
      try {
        const data = await getOverview();
        setOverview(data);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to fetch field overview",
        );
      } finally {
        setLoading(false);
      }
    }

    fetchOverview();
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-50 items-center justify-center">
        <Spinner className="size-8 text-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <CircleAlert />
        <AlertTitle>Error loading field overview: {error}</AlertTitle>
      </Alert>
    );
  }

  if (!overview) {
    return (
      <Alert>
        <CircleAlert />
        <AlertTitle>No field overview data available.</AlertTitle>
      </Alert>
    );
  }

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-primary">Field Overview</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          As of {formatDate(overview.as_of)}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <CurrentStageCard
          current={overview.stage.current}
          currentSince={overview.stage.current_since}
        />

        <UpcomingStagesCard upcoming={overview.stage.upcoming} />

        <YieldCard metric={overview.metrics.predicted_yield} />

        <RatingsCard metrics={overview.metrics} />
      </div>
    </section>
  );
}
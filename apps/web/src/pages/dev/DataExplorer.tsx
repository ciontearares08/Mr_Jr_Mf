import { useEffect, useMemo, useState } from "react";
import Papa from "papaparse";

import MetricCard from "@/components/MetricCard";

import {
  Database,
  Columns3,
  Table2,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from "@/components/ui/table";

import { LineChart, Line, CartesianGrid, XAxis, YAxis } from "recharts";

import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";

type RawRow = Record<string, string | number | null>;
interface CsvRow {
  clock_today: Date;
  wheat_lai: number;
  [key: string]: string | number | Date | null;
}

const ROWS_PER_PAGE_OPTIONS = [10, 25, 50];
const PREVIEW_ROWS = 50;
const CSV_URL = "/assets/zealand_cleaned.csv";

export default function DataExplorer() {
  const [data, setData] = useState<CsvRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Pagination states
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(PREVIEW_ROWS);

  // Load CSV
  useEffect(() => {
    const loadCsv = async () => {
      try {
        const response = await fetch(CSV_URL);

        if (!response.ok) {
          throw new Error("Could not load CSV file");
        }

        const csvText = await response.text();

        const result = Papa.parse<RawRow>(csvText, {
          header: true,
          dynamicTyping: true,
          skipEmptyLines: true,
        });

        if (result.errors.length > 0) {
          throw new Error(`CSV parse error: ${result.errors[0].message}`);
        }
        //currently the dev server returns 200 even with a missing file
        //so this checks if current file is an apsim file
        if (!result.meta.fields?.includes("clock_today")) {
          throw new Error("This file has no clock_today column");
        }

        const parsedData = result.data.map((row) => {
          //converts date to ISO std, 2025-01-01 00:00:00 --> 2025-01-01T00:00:00
          const date = new Date(String(row.clock_today).replace(" ", "T"));

          if (Number.isNaN(date.getTime())) {
            throw new Error(`Invalid date: ${row.clock_today}`);
          }
          return {
            ...row,
            clock_today: date,
            wheat_lai: Number(row.wheat_lai),
          };
        });

        setData(parsedData);
        console.log("CSV processed");
      } catch (error) {
        setError(
          error instanceof Error
            ? error.message
            : "Failed to load the CSV file",
        );
      } finally {
        setLoading(false);
      }
    };

    loadCsv();
  }, []);

  // Get CSV columns
  const columns = data.length > 0 ? Object.keys(data[0]) : [];

  // Only the first PREVIEW_ROWS = 50 records are available in the table
  // const tableData = data.slice(0, PREVIEW_ROWS);

  // Pagination calculations
  const firstRow = page * rowsPerPage;

  const lastRow = Math.min(firstRow + rowsPerPage, data.length);

  const rowsOnThisPage = data.slice(firstRow, lastRow);

  const isFirstPage = page === 0;
  const isLastPage = lastRow >= data.length;

  function changeRowsPerPage(newRowsPerPage: number | null) {
    if (newRowsPerPage === null) return;

    setRowsPerPage(newRowsPerPage);
    setPage(0);
  }

  //formats numbers like 4.2e-06 --> 0.0000042 or 0.321829319823 --> 0.3218
  //takes the first non-zero digit after decimal point and includes 3 numbers from there (4 in total)
  function formatCSVDataNumbers(value: number): string {
    if (!Number.isFinite(value)) return String(value);
    //below takes just the decimal part 123.456789 --> 0.456789
    const fraction = Math.abs(value) % 1;
    if (fraction === 0) return String(value);
    //decimal place up to first non-zero digit + 3 = 4 digits total
    //caps at 20
    const decimal = Math.min(-Math.floor(Math.log10(fraction)) + 3, 20);

    //rounds the whole value and drops any trailing 's
    return value.toLocaleString("en-GB", {
      maximumFractionDigits: decimal,
      useGrouping: false,
    });
  }
  // Chart uses ALL CSV observations
  /*const chartData = data.map((row) => ({
    clock_today: row.clock_today.getTime(),
    wheat_lai: row.wheat_lai,
  }));*/

  //Chart uses only 50 records
  const chartData = useMemo(
    () =>
      data.map((row) => ({
        clock_today: row.clock_today.getTime(),
        wheat_lai: row.wheat_lai,
      })),
    [data],
  );

  const chartConfig = {
    wheat_lai: {
      label: "Wheat LAI",
      color: "var(--chart-1)",
    },
  } satisfies ChartConfig;

  // Dataset metrics
  const maxLai =
    data.length > 0
      ? Math.max(...data.map((row) => Number(row.wheat_lai) || 0))
      : 0;

  if (loading) {
    return (
      <div className="flex min-h-50 items-center justify-center">
        <Spinner className="size-8text-primary" />
      </div>
    );
  }
  if (error) {
    return (
      <Alert variant="destructive">
        <CircleAlert />
        <AlertTitle>Could not load the dataset: {error}</AlertTitle>
      </Alert>
    );
  }

  return (
    <div className="space-y-8">
      {/* PAGE HEADER */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight">
            APSIM Data Explorer
          </h1>

          <p className="text-sm text-muted-foreground">
            Developer tools / Simulation diagnostics
          </p>
        </div>

        {/* <div className="flex items-center gap-2">
          <span
            className={`h-2.5 w-2.5 rounded-full ${
              loading ? "bg-yellow-500" : "bg-green-500"
            }`}
          />

          <span className="text-sm font-medium">
            {loading ? "Loading CSV..." : "CSV Loaded Successfully"}
          </span>
        </div> */}
      </div>

      {/* DATASET METRICS */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <MetricCard
          title="Total Records"
          value={data.length}
          description="Records loaded from APSIM"
          icon={<Database className="size-5" />}
        />

        <MetricCard
          title="Dataset Variables"
          value={columns.length}
          description="Available CSV columns"
          icon={<Columns3 className="size-5" />}
        />

        <MetricCard
          title="Maximum LAI"
          value={maxLai.toFixed(2)}
          description="Highest wheat LAI reached"
          icon={<Table2 className="size-5" />}
        />
      </div>

      {/* LAI CHART */}
      <section className="space-y-4">
        <div>
          <h2 className="text-xl font-semibold">Wheat LAI over time</h2>

          <p className="text-sm text-muted-foreground">
            Complete APSIM simulation · {chartData.length} observations
          </p>
        </div>

        <Card>
          <CardContent className="pt-6">
            <ChartContainer config={chartConfig} className="h-[350px] w-full">
              <LineChart
                accessibilityLayer
                data={chartData}
                margin={{
                  left: 12,
                  right: 12,
                  top: 12,
                  bottom: 12,
                }}
              >
                <CartesianGrid vertical={false} />

                <XAxis
                  dataKey="clock_today"
                  type="number"
                  scale="time"
                  domain={["dataMin", "dataMax"]}
                  tickCount={8}
                  minTickGap={40}
                  tickFormatter={(value) =>
                    new Date(value).toLocaleDateString("en-GB", {
                      day: "numeric",
                      month: "short",
                    })
                  }
                  tickLine={false}
                  axisLine={false}
                />

                <YAxis tickLine={false} axisLine={false} />

                <ChartTooltip
                  content={
                    <ChartTooltipContent
                      labelFormatter={(_, payload) => {
                        const timestamp = Number(
                          payload?.[0]?.payload?.clock_today,
                        );

                        if (!Number.isFinite(timestamp)) {
                          return "Simulation date";
                        }

                        return new Date(timestamp).toLocaleDateString("en-GB", {
                          day: "numeric",
                          month: "long",
                          year: "numeric",
                        });
                      }}
                    />
                  }
                />

                <Line
                  dataKey="wheat_lai"
                  type="monotone"
                  stroke="var(--color-wheat_lai)"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ChartContainer>
          </CardContent>
        </Card>
      </section>

      {/* DATASET TABLE */}
      <section>
        <Card>
          <CardHeader>
            <CardTitle className="text-lg font-semibold">
              Dataset Preview
            </CardTitle>

            <CardDescription>
              First 50 records of the APSIM dataset · All available simulation
              variables.
            </CardDescription>
          </CardHeader>

          <CardContent>
            {/* TABLE */}
            <div className="w-full overflow-x-auto rounded-lg border">
              <Table className="min-w-max">
                <TableHeader className="bg-muted">
                  <TableRow>
                    {columns.map((column) => (
                      <TableHead
                        key={column}
                        className="whitespace-nowrap text-muted-foreground"
                      >
                        {column}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>

                <TableBody>
                  {rowsOnThisPage.map((row, index) => (
                    <TableRow key={firstRow + index}>
                      {columns.map((column) => (
                        <TableCell key={column} className="whitespace-nowrap">
                          {row[column] instanceof Date
                            ? row[column].toLocaleDateString("en-GB")
                            : typeof row[column] === "number"
                              ? formatCSVDataNumbers(row[column])
                              : String(row[column] ?? "")}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}

                  {data.length === 0 && (
                    <TableRow>
                      <TableCell
                        colSpan={Math.max(columns.length, 1)}
                        className="h-24 text-center text-muted-foreground"
                      >
                        No data available.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>

            {/* PAGINATION CONTROLS */}
            <div className="flex flex-col gap-4 pt-4 sm:flex-row sm:items-center sm:justify-end">
              {/* Rows per page */}
              <div className="flex items-center gap-2">
                <span className="whitespace-nowrap text-sm text-muted-foreground">
                  Rows per page
                </span>

                <Select value={rowsPerPage} onValueChange={changeRowsPerPage}>
                  <SelectTrigger size="sm">
                    <SelectValue />
                  </SelectTrigger>

                  <SelectContent>
                    {ROWS_PER_PAGE_OPTIONS.map((option) => (
                      <SelectItem key={option} value={option}>
                        {option}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Row information */}
              <span className="whitespace-nowrap text-sm">
                {data.length === 0
                  ? "0 of 0"
                  : `${firstRow + 1}–${lastRow} of ${data.length}`}
              </span>

              {/* Previous / Next buttons */}
              <div className="flex gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Previous page"
                  disabled={isFirstPage}
                  onClick={() => setPage((current) => current - 1)}
                >
                  <ChevronLeft />
                </Button>

                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Next page"
                  disabled={isLastPage}
                  onClick={() => setPage((current) => current + 1)}
                >
                  <ChevronRight />
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

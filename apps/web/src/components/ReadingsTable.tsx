import { useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Reading } from "../services/mock_api";

const ROWS_PER_PAGE_OPTIONS = [10, 25, 100];

interface ReadingsTableProps {
  data: Reading[];
}

export default function ReadingsTable({ data }: ReadingsTableProps) {
  // `page` starts at 0, so the first page is page 0
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  // Work out which slice of `data` to show on the current page
  const firstRow = page * rowsPerPage;
  const lastRow = Math.min(firstRow + rowsPerPage, data.length);
  const rowsOnThisPage = data.slice(firstRow, lastRow);

  const isFirstPage = page === 0;
  const isLastPage = lastRow >= data.length;

  function changeRowsPerPage(newRowsPerPage: number | null) {
    // The Select reports null if nothing is selected, which can't happen here
    if (newRowsPerPage === null) return;
    setRowsPerPage(newRowsPerPage);
    setPage(0); // Jump back to the first page so we never end up past the end
  }

  return (
    <div className="overflow-hidden rounded-xl border">
      <Table>
        <TableHeader className="bg-muted">
          <TableRow>
            <TableHead>Date</TableHead>
            <TableHead>Crop Stage</TableHead>
            <TableHead>Leaf Area Index (LAI)</TableHead>
            <TableHead>Biomass (kg/ha)</TableHead>
            <TableHead>Topsoil Moisture (PAW)</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rowsOnThisPage.map((row, index) => (
            <TableRow key={firstRow + index}>
              <TableCell>
                {row.clock_today ? row.clock_today.split(" ")[0] : "N/A"}
              </TableCell>
              <TableCell>
                {row.wheat_phenology_current_stage_name || "Fallow"}
              </TableCell>
              <TableCell>{Number(row.wheat_lai || 0).toFixed(2)}</TableCell>
              <TableCell>
                {Number(row.wheat_above_ground_wt || 0).toFixed(2)}
              </TableCell>
              <TableCell>
                {Number(row["soil_soilwater_paw(1)"] || 0).toFixed(3)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {/* Pagination controls */}
      <div className="flex items-center justify-end gap-6 border-t px-4 py-2 text-sm">
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground">Rows per page</span>
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

        <span>
          {firstRow + 1}–{lastRow} of {data.length}
        </span>

        <div className="flex gap-1">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Previous page"
            disabled={isFirstPage}
            onClick={() => setPage(page - 1)}
          >
            <ChevronLeft />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Next page"
            disabled={isLastPage}
            onClick={() => setPage(page + 1)}
          >
            <ChevronRight />
          </Button>
        </div>
      </div>
    </div>
  );
}

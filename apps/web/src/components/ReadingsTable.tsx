import { useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  TablePagination,
} from "@mui/material";

// You can export this interface or use the one from your mock_api.ts
export interface Reading {
  clock_today: string;
  wheat_lai: number;
  wheat_phenology_current_stage_name: string;
  wheat_above_ground_wt: number;
  "soil_soilwater_paw(1)": number;
}

interface ReadingsTableProps {
  data: any[]; // Using any[] to flexibly accept your mock CSV JSON array
}

export default function ReadingsTable({ data }: ReadingsTableProps) {
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  const handleChangePage = (_event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  return (
    <Paper
      elevation={2}
      sx={{ width: "100%", overflow: "hidden", borderRadius: 2 }}
    >
      <TableContainer sx={{ maxHeight: 600 }}>
        <Table stickyHeader aria-label="telemetry table">
          <TableHead>
            <TableRow>
              <TableCell
                sx={{ fontWeight: "bold", backgroundColor: "#f3f4f6" }}
              >
                Date
              </TableCell>
              <TableCell
                sx={{ fontWeight: "bold", backgroundColor: "#f3f4f6" }}
              >
                Crop Stage
              </TableCell>
              <TableCell
                sx={{ fontWeight: "bold", backgroundColor: "#f3f4f6" }}
              >
                Leaf Area Index (LAI)
              </TableCell>
              <TableCell
                sx={{ fontWeight: "bold", backgroundColor: "#f3f4f6" }}
              >
                Biomass (kg/ha)
              </TableCell>
              <TableCell
                sx={{ fontWeight: "bold", backgroundColor: "#f3f4f6" }}
              >
                Topsoil Moisture (PAW)
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data
              .slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)
              .map((row, index) => (
                <TableRow hover role="checkbox" tabIndex={-1} key={index}>
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
      </TableContainer>
      <TablePagination
        rowsPerPageOptions={[10, 25, 100]}
        component="div"
        count={data.length}
        rowsPerPage={rowsPerPage}
        page={page}
        onPageChange={handleChangePage}
        onRowsPerPageChange={handleChangeRowsPerPage}
      />
    </Paper>
  );
}

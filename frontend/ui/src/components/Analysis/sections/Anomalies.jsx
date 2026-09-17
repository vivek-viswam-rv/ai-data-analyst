import { Card, CardContent, CardHeader, CardTitle } from "shadcn/card";
import { Separator } from "shadcn/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "shadcn/table";

const Anomalies = ({ report }) => (
  <Card>
    <CardHeader>
      <CardTitle>Anomalies</CardTitle>
    </CardHeader>
    <CardContent className="flex flex-col gap-4">
      <p className="text-muted-foreground">{report.summary}</p>
      <p className="text-lg font-semibold">
        {report.total_flagged} anomalies flagged
      </p>

      {report.groups.length === 0 ? (
        <p className="text-sm text-muted-foreground">No anomalies detected.</p>
      ) : (
        <div className="flex flex-col gap-4">
          {report.groups.map((group, index) => (
            <div key={group.id}>
              {index > 0 && <Separator className="mb-4" />}
              <div className="flex flex-col gap-2 rounded-lg border p-4">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="font-semibold">{group.method}</span>
                  <span className="text-sm text-muted-foreground">
                    {group.count} flagged
                  </span>
                </div>
                <p className="text-sm text-muted-foreground">
                  Columns: {group.columns.join(", ")}
                </p>
                <p className="text-sm">{group.description}</p>
                <p className="text-sm text-muted-foreground">
                  {group.interpretation}
                </p>

                {group.example_columns.length > 0 &&
                  group.example_rows.length > 0 && (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          {group.example_columns.map((column) => (
                            <TableHead key={column}>{column}</TableHead>
                          ))}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {group.example_rows.map((row, rowIndex) => (
                          <TableRow key={rowIndex}>
                            {row.map((cell, cellIndex) => (
                              <TableCell key={cellIndex}>{cell}</TableCell>
                            ))}
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
              </div>
            </div>
          ))}
        </div>
      )}
    </CardContent>
  </Card>
);

export default Anomalies;

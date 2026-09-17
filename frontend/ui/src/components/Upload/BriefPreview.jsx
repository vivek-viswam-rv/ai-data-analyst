import { Badge } from "shadcn/badge";
import { Card, CardContent, CardHeader, CardTitle } from "shadcn/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "shadcn/table";

const KIND_BADGE_CLASSES = {
  numeric: "border-blue-500/40 text-blue-600 dark:text-blue-400",
  datetime: "border-purple-500/40 text-purple-600 dark:text-purple-400",
  categorical: "border-green-500/40 text-green-600 dark:text-green-400",
  boolean: "border-amber-500/40 text-amber-600 dark:text-amber-400",
  text: "",
  empty: "",
};

const KIND_BADGE_VARIANT = {
  empty: "destructive",
  text: "secondary",
};

const BriefPreview = ({ brief }) => {
  const columns = brief.columns ?? [];
  const previewRows = brief.preview ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>{brief.filename}</CardTitle>
        <p className="text-sm text-muted-foreground">
          {brief.n_rows} rows × {brief.n_cols} columns
          {brief.sampled && (
            <span className="ml-1">
              (sampled from {brief.original_rows} rows)
            </span>
          )}
        </p>
      </CardHeader>
      <CardContent className="space-y-6">
        <div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Null %</TableHead>
                <TableHead>Unique</TableHead>
                <TableHead>Sample values</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {columns.map((col) => (
                <TableRow key={col.name}>
                  <TableCell className="font-medium">{col.name}</TableCell>
                  <TableCell>
                    <Badge
                      variant={KIND_BADGE_VARIANT[col.kind] ?? "outline"}
                      className={KIND_BADGE_CLASSES[col.kind]}
                    >
                      {col.kind}
                    </Badge>
                  </TableCell>
                  <TableCell>{col.null_pct.toFixed(1)}%</TableCell>
                  <TableCell>{col.unique}</TableCell>
                  <TableCell>
                    <span className="block max-w-xs truncate text-muted-foreground">
                      {col.sample_values.join(", ")}
                    </span>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        <div>
          <p className="mb-2 text-sm font-medium text-foreground">Preview</p>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  {columns.map((col) => (
                    <TableHead key={col.name}>{col.name}</TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {previewRows.map((row, rowIndex) => (
                  <TableRow key={rowIndex}>
                    {columns.map((col) => (
                      <TableCell key={`${rowIndex}-${col.name}`}>
                        {row[col.name] ?? ""}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default BriefPreview;

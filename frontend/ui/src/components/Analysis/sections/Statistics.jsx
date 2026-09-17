import { Card, CardContent, CardHeader, CardTitle } from "shadcn/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "shadcn/table";
import { formatPValue, formatSignificant } from "utils/report";

const effectSizeLabel = (test) =>
  test.effect_size_name
    ? `${test.effect_size_name}: ${formatSignificant(test.effect_size)}`
    : "—";

const Statistics = ({ report }) => (
  <Card>
    <CardHeader>
      <CardTitle>Statistical tests</CardTitle>
    </CardHeader>
    <CardContent className="flex flex-col gap-4">
      <p className="text-muted-foreground">{report.summary}</p>

      {report.tests.length === 0 ? (
        <p className="text-sm text-muted-foreground">No tests were run.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Test</TableHead>
              <TableHead>Columns</TableHead>
              <TableHead>Statistic</TableHead>
              <TableHead>p-value</TableHead>
              <TableHead>Effect size</TableHead>
              <TableHead>Conclusion</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {report.tests.map((test) => (
              <TableRow key={test.id}>
                <TableCell>{test.name}</TableCell>
                <TableCell>{test.columns.join(", ")}</TableCell>
                <TableCell>{formatSignificant(test.statistic)}</TableCell>
                <TableCell>{formatPValue(test.p_value)}</TableCell>
                <TableCell>{effectSizeLabel(test)}</TableCell>
                <TableCell className="whitespace-normal">
                  {test.conclusion}
                  {test.caveats.length > 0 && (
                    <details className="mt-1 text-xs text-muted-foreground">
                      <summary className="cursor-pointer select-none">
                        Caveats
                      </summary>
                      <ul className="list-disc space-y-0.5 pl-4 pt-1">
                        {test.caveats.map((caveat) => (
                          <li key={caveat}>{caveat}</li>
                        ))}
                      </ul>
                    </details>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </CardContent>
  </Card>
);

export default Statistics;

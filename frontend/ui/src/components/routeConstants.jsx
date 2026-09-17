import NotFound from "./commons/NotFound";
import Upload from "./Upload";

export const HOME_ROUTE = "/";
export const ANALYSIS_ROUTE = "/analysis";

export const ROUTES = [
  {
    path: HOME_ROUTE,
    element: <Upload />,
  },
  {
    path: "*",
    element: <NotFound />,
  },
];

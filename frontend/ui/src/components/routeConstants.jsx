import NotFound from "./commons/NotFound";
import Upload from "./Upload";
import Analysis from "./Analysis";

export const HOME_ROUTE = "/";
export const ANALYSIS_ROUTE = "/analysis";

export const ROUTES = [
  {
    path: HOME_ROUTE,
    element: <Upload />,
  },
  {
    path: ANALYSIS_ROUTE,
    element: <Analysis />,
  },
  {
    path: "*",
    element: <NotFound />,
  },
];

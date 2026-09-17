import NotFound from "./commons/NotFound";
import Home from "./Home";

export const HOME_ROUTE = "/";

export const ROUTES = [
  {
    path: HOME_ROUTE,
    element: <Home />,
  },
  {
    path: "*",
    element: <NotFound />,
  },
];

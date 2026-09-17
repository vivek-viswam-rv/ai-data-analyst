import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { ROUTES } from "./routeConstants";

const router = createBrowserRouter(ROUTES);

const App = () => <RouterProvider router={router} />;

export default App;

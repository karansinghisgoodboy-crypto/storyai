// Small shared state for the page.
const State = {
  currentProject: null, // the project open in the workspace, or null
  navId: 0, // bumped on every screen change so slow requests can't draw over a newer screen
};

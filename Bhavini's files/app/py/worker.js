/* NOMAD in the browser: a worker that starts Python (Pyodide, MPL-2.0) and runs app/code/nomad_web.py, the same NOMAD
   code as Rhino (layout, better, flags, nomad_core, nomad_model, prisms). The page sends {id, request}; the worker answers
   {id, result} or {id, error}. Python's standard library ships base64 inside python_stdlib.json (the host serves no zip). */
importScripts("pyodide.js");
// NOMAD's own code, read straight from the step folders (no copies): module -> folder
const MODULES = {layout: "7_floor_plans/code", better: "7_floor_plans/code", plan2: "7_floor_plans/code", library_fit: "7_floor_plans/code",
  furnish: "7_floor_plans/code", own_plans: "7_floor_plans/code", plan3: "7_floor_plans/code", building: "7_floor_plans/code",
  shared: "7_floor_plans/code", prisms: "7_floor_plans/code", flags: "6_check_the_shop/code", nomad_core: "rhino_grasshopper/code",
  nomad_model: "rhino_grasshopper/code", nomad_web: "app/code"};
let ready = null;

async function boot() {
  const base = new URL("./", self.location.href).href;
  const j = await (await fetch(base + "python_stdlib.json")).json();
  const bin = Uint8Array.from(atob(j.b64), c => c.charCodeAt(0));
  const stdLibURL = URL.createObjectURL(new Blob([bin], { type: "application/zip" }));
  const py = await loadPyodide({ indexURL: base, stdLibURL });
  py.FS.mkdirTree("/nomad");
  const top = new URL("../../", self.location.href).href;          // the nomad folder
  const get = async (rel) => (await fetch(top + rel, { cache: "no-cache" })).text();
  for (const [m, dir] of Object.entries(MODULES)) py.FS.writeFile("/nomad/" + m + ".py", await get(dir + "/" + m + ".py"));
  py.FS.writeFile("/nomad/library_street.json", await get("7_floor_plans/output/library/library_street.json"));   // the real flats (plan3)
  py.FS.writeFile("/nomad/fit_table.json", await get("7_floor_plans/output/library/fit_table.json"));   // which plans can pass at each size
  py.runPython("import sys; sys.path.insert(0, '/nomad'); import nomad_web");
  return py;
}

self.onmessage = async e => {
  const { id, request } = e.data;
  try {
    if (!ready) ready = boot();
    const py = await ready;
    if (request === "ping") { self.postMessage({ id, result: "ready" }); return; }
    py.globals.set("REQ", JSON.stringify(request));
    const out = py.runPython("nomad_web.run(REQ)");
    self.postMessage({ id, result: JSON.parse(out) });
  } catch (err) {
    self.postMessage({ id, error: String(err && err.message || err).slice(-1500) });
  }
};

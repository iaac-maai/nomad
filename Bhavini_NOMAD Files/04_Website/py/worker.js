/* NOMAD in the browser: a worker that starts Python (Pyodide, MPL-2.0) and runs src/app/nomad_web.py, the same NOMAD
   code as Rhino (layout, better, flags, nomad_core, nomad_model, prisms). The page sends {id, request}; the worker answers
   {id, result} or {id, error}. Python's standard library ships base64 inside python_stdlib.json (the host serves no zip). */
importScripts("pyodide.js");
const MODULES = ["layout", "better", "plan2", "library_fit", "furnish", "own_plans", "plan3", "building", "shared", "flags", "nomad_core", "nomad_model", "prisms", "nomad_web"];
let ready = null;

async function boot() {
  const base = new URL("./", self.location.href).href;
  const j = await (await fetch(base + "python_stdlib.json")).json();
  const bin = Uint8Array.from(atob(j.b64), c => c.charCodeAt(0));
  const stdLibURL = URL.createObjectURL(new Blob([bin], { type: "application/zip" }));
  const py = await loadPyodide({ indexURL: base, stdLibURL });
  py.FS.mkdirTree("/nomad");
  for (const m of MODULES) py.FS.writeFile("/nomad/" + m + ".py", await (await fetch(base + "src/" + m + ".txt")).text());
  py.FS.writeFile("/nomad/library_street.json", await (await fetch(base + "src/library_street.json")).text());   // the real flats (plan3)
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

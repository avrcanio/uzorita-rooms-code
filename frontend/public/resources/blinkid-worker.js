var Le = Object.defineProperty;
var J = (e) => {
  throw TypeError(e);
};
var Oe = (e, t, r) => t in e ? Le(e, t, { enumerable: !0, configurable: !0, writable: !0, value: r }) : e[t] = r;
var x = (e, t, r) => Oe(e, typeof t != "symbol" ? t + "" : t, r), $ = (e, t, r) => t.has(e) || J("Cannot " + r);
var u = (e, t, r) => ($(e, t, "read from private field"), r ? r.call(e) : t.get(e)), p = (e, t, r) => t.has(e) ? J("Cannot add the same private member more than once") : t instanceof WeakSet ? t.add(e) : t.set(e, r), y = (e, t, r, o) => ($(e, t, "write to private field"), o ? o.call(e, r) : t.set(e, r), r), R = (e, t, r) => ($(e, t, "access private method"), r);
var Q = (e, t, r, o) => ({
  set _(s) {
    y(e, t, s, r);
  },
  get _() {
    return u(e, t, o);
  }
});
/**
 * @license
 * Copyright 2019 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */
const ae = Symbol("Comlink.proxy"), Re = Symbol("Comlink.endpoint"), ve = Symbol("Comlink.releaseProxy"), z = Symbol("Comlink.finalizer"), W = Symbol("Comlink.thrown"), ie = (e) => typeof e == "object" && e !== null || typeof e == "function", Ae = {
  canHandle: (e) => ie(e) && e[ae],
  serialize(e) {
    const { port1: t, port2: r } = new MessageChannel();
    return H(e, t), [r, [r]];
  },
  deserialize(e) {
    return e.start(), Ie(e);
  }
}, Ue = {
  canHandle: (e) => ie(e) && W in e,
  serialize({ value: e }) {
    let t;
    return e instanceof Error ? t = {
      isError: !0,
      value: {
        message: e.message,
        name: e.name,
        stack: e.stack
      }
    } : t = { isError: !1, value: e }, [t, []];
  },
  deserialize(e) {
    throw e.isError ? Object.assign(new Error(e.value.message), e.value) : e.value;
  }
}, ce = /* @__PURE__ */ new Map([
  ["proxy", Ae],
  ["throw", Ue]
]);
function Te(e, t) {
  for (const r of e)
    if (t === r || r === "*" || r instanceof RegExp && r.test(t))
      return !0;
  return !1;
}
function H(e, t = globalThis, r = ["*"]) {
  t.addEventListener("message", function o(s) {
    if (!s || !s.data)
      return;
    if (!Te(r, s.origin)) {
      console.warn(`Invalid origin '${s.origin}' for comlink proxy`);
      return;
    }
    const { id: n, type: m, path: a } = Object.assign({ path: [] }, s.data), c = (s.data.argumentList || []).map(k);
    let i;
    try {
      const l = a.slice(0, -1).reduce((f, w) => f[w], e), d = a.reduce((f, w) => f[w], e);
      switch (m) {
        case "GET":
          i = d;
          break;
        case "SET":
          l[a.slice(-1)[0]] = k(s.data.value), i = !0;
          break;
        case "APPLY":
          i = d.apply(l, c);
          break;
        case "CONSTRUCT":
          {
            const f = new d(...c);
            i = he(f);
          }
          break;
        case "ENDPOINT":
          {
            const { port1: f, port2: w } = new MessageChannel();
            H(e, w), i = me(f, [f]);
          }
          break;
        case "RELEASE":
          i = void 0;
          break;
        default:
          return;
      }
    } catch (l) {
      i = { value: l, [W]: 0 };
    }
    Promise.resolve(i).catch((l) => ({ value: l, [W]: 0 })).then((l) => {
      const [d, f] = j(l);
      t.postMessage(Object.assign(Object.assign({}, d), { id: n }), f), m === "RELEASE" && (t.removeEventListener("message", o), le(t), z in e && typeof e[z] == "function" && e[z]());
    }).catch((l) => {
      const [d, f] = j({
        value: new TypeError("Unserializable return value"),
        [W]: 0
      });
      t.postMessage(Object.assign(Object.assign({}, d), { id: n }), f);
    });
  }), t.start && t.start();
}
function Me(e) {
  return e.constructor.name === "MessagePort";
}
function le(e) {
  Me(e) && e.close();
}
function Ie(e, t) {
  const r = /* @__PURE__ */ new Map();
  return e.addEventListener("message", function(s) {
    const { data: n } = s;
    if (!n || !n.id)
      return;
    const m = r.get(n.id);
    if (m)
      try {
        m(n);
      } finally {
        r.delete(n.id);
      }
  }), _(e, r, [], t);
}
function M(e) {
  if (e)
    throw new Error("Proxy has been released and is not useable");
}
function ue(e) {
  return L(e, /* @__PURE__ */ new Map(), {
    type: "RELEASE"
  }).then(() => {
    le(e);
  });
}
const B = /* @__PURE__ */ new WeakMap(), C = "FinalizationRegistry" in globalThis && new FinalizationRegistry((e) => {
  const t = (B.get(e) || 0) - 1;
  B.set(e, t), t === 0 && ue(e);
});
function Ne(e, t) {
  const r = (B.get(t) || 0) + 1;
  B.set(t, r), C && C.register(e, t, e);
}
function ze(e) {
  C && C.unregister(e);
}
function _(e, t, r = [], o = function() {
}) {
  let s = !1;
  const n = new Proxy(o, {
    get(m, a) {
      if (M(s), a === ve)
        return () => {
          ze(n), ue(e), t.clear(), s = !0;
        };
      if (a === "then") {
        if (r.length === 0)
          return { then: () => n };
        const c = L(e, t, {
          type: "GET",
          path: r.map((i) => i.toString())
        }).then(k);
        return c.then.bind(c);
      }
      return _(e, t, [...r, a]);
    },
    set(m, a, c) {
      M(s);
      const [i, l] = j(c);
      return L(e, t, {
        type: "SET",
        path: [...r, a].map((d) => d.toString()),
        value: i
      }, l).then(k);
    },
    apply(m, a, c) {
      M(s);
      const i = r[r.length - 1];
      if (i === Re)
        return L(e, t, {
          type: "ENDPOINT"
        }).then(k);
      if (i === "bind")
        return _(e, t, r.slice(0, -1));
      const [l, d] = Z(c);
      return L(e, t, {
        type: "APPLY",
        path: r.map((f) => f.toString()),
        argumentList: l
      }, d).then(k);
    },
    construct(m, a) {
      M(s);
      const [c, i] = Z(a);
      return L(e, t, {
        type: "CONSTRUCT",
        path: r.map((l) => l.toString()),
        argumentList: c
      }, i).then(k);
    }
  });
  return Ne(n, e), n;
}
function We(e) {
  return Array.prototype.concat.apply([], e);
}
function Z(e) {
  const t = e.map(j);
  return [t.map((r) => r[0]), We(t.map((r) => r[1]))];
}
const de = /* @__PURE__ */ new WeakMap();
function me(e, t) {
  return de.set(e, t), e;
}
function he(e) {
  return Object.assign(e, { [ae]: !0 });
}
function j(e) {
  for (const [t, r] of ce)
    if (r.canHandle(e)) {
      const [o, s] = r.serialize(e);
      return [
        {
          type: "HANDLER",
          name: t,
          value: o
        },
        s
      ];
    }
  return [
    {
      type: "RAW",
      value: e
    },
    de.get(e) || []
  ];
}
function k(e) {
  switch (e.type) {
    case "HANDLER":
      return ce.get(e.name).deserialize(e.value);
    case "RAW":
      return e.value;
  }
}
function L(e, t, r, o) {
  return new Promise((s) => {
    const n = De();
    t.set(n, s), e.start && e.start(), e.postMessage(Object.assign({ id: n }, r), o);
  });
}
function De() {
  return new Array(4).fill(0).map(() => Math.floor(Math.random() * Number.MAX_SAFE_INTEGER).toString(16)).join("-");
}
const Be = async () => WebAssembly.validate(new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0, 1, 4, 1, 96, 0, 0, 3, 2, 1, 0, 5, 3, 1, 0, 1, 10, 14, 1, 12, 0, 65, 0, 65, 0, 65, 0, 252, 10, 0, 0, 11])), Ce = async () => WebAssembly.validate(new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0, 2, 8, 1, 1, 97, 1, 98, 3, 127, 1, 6, 6, 1, 127, 1, 65, 0, 11, 7, 5, 1, 1, 97, 3, 1])), je = async () => WebAssembly.validate(new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0, 1, 4, 1, 96, 0, 0, 3, 2, 1, 0, 10, 7, 1, 5, 0, 208, 112, 26, 11])), Ve = async () => WebAssembly.validate(new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0, 1, 4, 1, 96, 0, 0, 3, 2, 1, 0, 10, 12, 1, 10, 0, 67, 0, 0, 0, 0, 252, 0, 26, 11])), $e = async () => WebAssembly.validate(new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0, 1, 4, 1, 96, 0, 0, 3, 2, 1, 0, 10, 8, 1, 6, 0, 65, 0, 192, 26, 11])), Fe = async () => WebAssembly.validate(new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0, 1, 5, 1, 96, 0, 1, 123, 3, 2, 1, 0, 10, 10, 1, 8, 0, 65, 0, 253, 15, 253, 98, 11])), _e = () => (async (e) => {
  try {
    return typeof MessageChannel < "u" && new MessageChannel().port1.postMessage(new SharedArrayBuffer(1)), WebAssembly.validate(e);
  } catch {
    return !1;
  }
})(new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0, 1, 4, 1, 96, 0, 0, 3, 2, 1, 0, 5, 4, 1, 3, 1, 1, 10, 11, 1, 9, 0, 65, 0, 254, 16, 2, 0, 26, 11]));
function He() {
  const e = navigator.userAgent.toLowerCase();
  return e.includes("safari") && !e.includes("chrome");
}
async function qe() {
  if (!await _e()) return !1;
  if (!("importScripts" in self))
    throw Error("Not implemented");
  return He() ? !1 : "Worker" in self;
}
async function Ge() {
  const e = [
    Ce(),
    je(),
    Be(),
    Ve(),
    $e()
  ];
  if (!(await Promise.all(e)).every(Boolean))
    throw new Error("Browser doesn't meet minimum requirements!");
  return await Fe() ? await qe() ? "advanced-threads" : "advanced" : "basic";
}
const ee = "application/javascript", Ye = (e, t = {}) => {
  const r = {
    skipSameOrigin: !0,
    useBlob: !0,
    ...t
  };
  return r.skipSameOrigin && new URL(e).origin === self.location.origin ? Promise.resolve(e) : new Promise(
    (o, s) => void fetch(e).then((n) => n.text()).then((n) => {
      new URL(e).href.split("/").pop();
      let a = "";
      if (r.useBlob) {
        const c = new Blob([n], { type: ee });
        a = URL.createObjectURL(c);
      } else
        a = `data:${ee},` + encodeURIComponent(n);
      o(a);
    }).catch(s)
  );
};
function Ke() {
  const e = self.navigator.userAgent.toLowerCase();
  return /iphone|ipad|ipod/.test(e);
}
function Xe(e) {
  return {
    licenseId: e.licenseId,
    licensee: e.licensee,
    applicationIds: e.applicationIds,
    packageName: e.packageName,
    platform: "Browser",
    sdkName: e.sdkName,
    sdkVersion: e.sdkVersion
  };
}
async function te(e, t = "https://baltazar.microblink.com/api/v2/status/check") {
  if (!t || typeof t != "string")
    throw new Error("Invalid baltazarUrl: must be a non-empty string");
  try {
    new URL(t);
  } catch {
    throw new Error(`Invalid baltazarUrl format: ${t}`);
  }
  try {
    const r = await fetch(t, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      cache: "no-cache",
      body: JSON.stringify(Xe(e))
    });
    if (!r.ok)
      throw new Error(
        `Server returned error: ${r.status} ${r.statusText}`
      );
    return await r.text();
  } catch (r) {
    throw console.error("Server permission request failed:", r), r;
  }
}
function re(e) {
  return Math.ceil(e * 1024 * 1024 / 64 / 1024);
}
function I(...e) {
  const t = e.filter((r) => r).join("/").replace(/([^:]\/)\/+/g, "$1");
  try {
    new URL(t, "http://example.com");
  } catch {
    throw new Error(`Invalid URL: ${t}`);
  }
  return t;
}
function fe(e) {
  return Object.prototype.toString.call(e).slice(8, -1);
}
function N(e) {
  if (fe(e) !== "Object")
    return !1;
  const t = Object.getPrototypeOf(e);
  return !!t && t.constructor === Object && t === Object.prototype;
}
function ne(e) {
  return fe(e) === "Symbol";
}
function se(e, t, r, o) {
  const s = {}.propertyIsEnumerable.call(o, t) ? "enumerable" : "nonenumerable";
  s === "enumerable" && (e[t] = r), s === "nonenumerable" && Object.defineProperty(e, t, {
    value: r,
    enumerable: !1,
    writable: !0,
    configurable: !0
  });
}
function ge(e, t, r) {
  if (!N(t))
    return t;
  let o = {};
  if (N(e)) {
    const a = Object.getOwnPropertyNames(e), c = Object.getOwnPropertySymbols(e);
    o = [...a, ...c].reduce((i, l) => {
      const d = e[l];
      return (!ne(l) && !Object.getOwnPropertyNames(t).includes(l) || ne(l) && !Object.getOwnPropertySymbols(t).includes(l)) && se(i, l, d, e), i;
    }, {});
  }
  const s = Object.getOwnPropertyNames(t), n = Object.getOwnPropertySymbols(t);
  return [...s, ...n].reduce((a, c) => {
    let i = t[c];
    const l = N(e) ? e[c] : void 0;
    return l !== void 0 && N(i) && (i = ge(l, i)), se(a, c, i, t), a;
  }, o);
}
function Je(e, ...t) {
  return t.reduce((r, o) => ge(r, o), e);
}
function pe(e) {
  return {
    country: (e == null ? void 0 : e.country) ?? void 0,
    region: (e == null ? void 0 : e.region) ?? void 0,
    type: (e == null ? void 0 : e.type) ?? void 0
  };
}
const Qe = (e) => ({
  documentFilter: pe(e.documentFilter),
  fields: e.fields ?? []
}), Ze = (e) => ({
  documentFilter: pe(e.documentFilter),
  fields: e.fields || [],
  documentNumberAnonymizationSettings: e.documentNumberAnonymizationSettings ? {
    prefixDigitsVisible: e.documentNumberAnonymizationSettings.prefixDigitsVisible,
    suffixDigitsVisible: e.documentNumberAnonymizationSettings.suffixDigitsVisible
  } : void 0
});
function et(e = {}, t) {
  var m, a, c, i;
  e && (e = Object.fromEntries(
    Object.entries(e).filter(([l, d]) => d !== void 0)
  ));
  const r = ((a = (m = e == null ? void 0 : e.scanningSettings) == null ? void 0 : m.customDocumentRules) == null ? void 0 : a.map(
    Qe
  )) ?? [], o = ((i = (c = e == null ? void 0 : e.scanningSettings) == null ? void 0 : c.customDocumentAnonymizationSettings) == null ? void 0 : i.map(
    Ze
  )) ?? [], s = {
    ...e == null ? void 0 : e.scanningSettings,
    customDocumentRules: r,
    customDocumentAnonymizationSettings: o
  };
  return Je(t, {
    ...e,
    scanningSettings: s
  });
}
const tt = { basic: { full: 3242861, lightweight: 3280274 }, advanced: { full: 3261875, lightweight: 3298460 }, "advanced-threads": { full: 3308759, lightweight: 3343810 } }, rt = { basic: { full: 13393962, lightweight: 11761277 }, advanced: { full: 13393962, lightweight: 11761277 }, "advanced-threads": { full: 13393962, lightweight: 11761277 } }, nt = {
  wasm: tt,
  data: rt
};
function st(e, t, r) {
  return nt[e][t][r];
}
async function oe(e, t, r, o, s) {
  var d;
  const n = await fetch(e);
  if (!s)
    return n.arrayBuffer();
  const m = n.headers.get("Content-Length"), a = m ? parseInt(m, 10) : st(t, r, o);
  if (isNaN(a) || a <= 0)
    throw new Error(
      `Invalid content length for ${t} file: ${a}`
    );
  let c = 0;
  const i = new TransformStream({
    transform(f, w) {
      c += f.length;
      const V = Math.min(
        Math.round(c / a * 100),
        100
      );
      s({
        loaded: c,
        contentLength: a,
        progress: V,
        finished: !1
      }), w.enqueue(f);
    },
    flush() {
      s({
        loaded: c,
        contentLength: a,
        progress: 100,
        finished: !0
      });
    }
  });
  return new Response(
    (d = n.body) == null ? void 0 : d.pipeThrough(i),
    n
  ).arrayBuffer();
}
class F extends Error {
  constructor(t, r, o) {
    super(`Proxy URL validation failed for "${o}": ${r}`), this.code = t, this.url = o, this.name = "ProxyUrlValidationError";
  }
}
function ot(e) {
  const t = e.unlockResult === "requires-server-permission", { allowPingProxy: r, allowBaltazarProxy: o, hasPing: s } = e;
  if (!r && !o)
    throw new Error(
      "Microblink proxy URL is set but your license doesn't permit proxy usage. Check your license."
    );
  if (!t && !s)
    throw new Error(
      "Microblink proxy URL is set but your license doesn't permit proxy usage. Check your license."
    );
  if (!t && s && o && !r || t && !s && !o && r)
    throw new Error(
      "Microblink proxy URL is set but your license doesn't permit proxy usage. Check your license."
    );
}
function at(e) {
  let t;
  try {
    t = new URL(e);
  } catch {
    throw new F(
      "INVALID_PROXY_URL",
      `Failed to create URL instance for provided Microblink proxy URL "${e}". Expected format: https://your-proxy.com or https://your-proxy.com/`,
      e
    );
  }
  if (t.protocol !== "https:")
    throw new F(
      "HTTPS_REQUIRED",
      `Proxy URL validation failed for "${e}": HTTPS protocol must be used. Expected format: https://your-proxy.com or https://your-proxy.com/`,
      e
    );
  const r = t.origin;
  try {
    const o = new URL(
      `${t.pathname}${t.pathname.endsWith("/") ? "" : "/"}api/v2/status/check`,
      r
    ).toString();
    return {
      ping: r + t.pathname.replace(/\/$/, ""),
      baltazar: o
    };
  } catch {
    throw new F(
      "INVALID_PROXY_URL",
      "Failed to build baltazar service URL",
      e
    );
  }
}
var h, v, A, U, T, b, O, P, ye, D;
class it {
  constructor() {
    p(this, P);
    /**
     * The Wasm module.
     */
    p(this, h);
    /**
     * The default session settings.
     *
     * Must be initialized when calling initBlinkId.
     */
    p(this, v);
    /**
     * The progress status callback.
     */
    x(this, "progressStatusCallback");
    /**
     * Whether the demo overlay is shown.
     */
    p(this, A, !0);
    /**
     * Whether the production overlay is shown.
     */
    p(this, U, !0);
    /**
     * Current session number.
     */
    p(this, T, 0);
    /**
     * Sanitized proxy URLs for Microblink services.
     */
    p(this, b);
    p(this, O);
  }
  reportPinglet(t) {
    if (!u(this, h))
      throw new Error("Wasm module not loaded");
    u(this, h).isPingEnabled() && u(this, h).queuePinglet(
      JSON.stringify(t.data),
      t.schemaName,
      t.schemaVersion,
      // session number can be overriden by pinglet, otherwise use current
      // session count
      t.sessionNumber ?? u(this, T)
    );
  }
  sendPinglets() {
    if (!u(this, h))
      throw new Error("Wasm module not loaded");
    u(this, h).sendPinglets();
  }
  /**
   * This method initializes everything.
   */
  async initBlinkId(t, r, o) {
    var a;
    const s = new URL(
      "resources/",
      t.resourcesLocation
    ).toString();
    if (y(this, v, r), this.progressStatusCallback = o, y(this, O, t.userId), await R(this, P, ye).call(this, {
      resourceUrl: s,
      variant: t.wasmVariant,
      initialMemory: t.initialMemory,
      useLightweightBuild: t.useLightweightBuild
    }), !u(this, h))
      throw new Error("Wasm module not loaded");
    const n = u(this, h).initializeWithLicenseKey(
      t.licenseKey,
      t.userId,
      !1
    );
    t.microblinkProxyUrl && (ot(n), y(this, b, at(t.microblinkProxyUrl)), n.allowPingProxy && n.hasPing && (u(this, h).setPingProxyUrl(u(this, b).ping), console.debug(`Using ping proxy URL: ${u(this, b).ping}`)));
    const m = new lt({
      packageName: self.location.hostname,
      platform: "Emscripten",
      product: "BlinkID",
      userId: u(this, O)
    });
    if (this.reportPinglet(m), this.sendPinglets(), n.licenseError)
      throw R(this, P, D).call(this, {
        errorType: "Crash",
        errorMessage: n.licenseError
      }), this.sendPinglets(), new ut(
        "License unlock error: " + n.licenseError,
        "LICENSE_ERROR"
      );
    if (n.unlockResult === "requires-server-permission") {
      const i = ((a = u(this, b)) == null ? void 0 : a.baltazar) && n.allowBaltazarProxy ? u(this, b).baltazar : void 0;
      i && console.debug(`Using Baltazar proxy URL: ${i}`);
      const l = i ? await te(n, i) : await te(n), d = u(this, h).submitServerPermission(
        l
      );
      if (d != null && d.error)
        throw R(this, P, D).call(this, {
          errorType: "Crash",
          errorMessage: d.error
        }), this.sendPinglets(), new Error("Server unlock error: " + d.error);
    }
    console.debug(`BlinkID SDK ${n.sdkVersion} unlocked`), y(this, A, n.showDemoOverlay), y(this, U, n.showProductionOverlay), u(this, h).initializeSdk(t.userId), this.sendPinglets();
  }
  /**
   * This method creates a BlinkID scanning session.
   *
   * @param options - The options for the session.
   * @returns The session.
   */
  createBlinkIdScanningSession(t) {
    if (!u(this, h))
      throw new Error("Wasm module not loaded");
    const r = et(
      t,
      u(this, v)
    ), o = u(this, h).createBlinkIdScanningSession(
      r,
      u(this, O)
    );
    return this.sendPinglets(), Q(this, T)._++, this.createProxySession(o, r);
  }
  /**
   * This method creates a proxy session.
   *
   * @param session - The session.
   * @param sessionSettings - The session settings.
   * @returns The proxy session.
   */
  createProxySession(t, r) {
    return he({
      getResult: () => t.getResult(),
      process: (s) => {
        const n = t.process(s);
        if ("error" in n)
          throw R(this, P, D).call(this, {
            errorType: "NonFatal",
            errorMessage: n.error
          }), new Error(`Error processing frame: ${n.error}`);
        return me(
          {
            ...n,
            arrayBuffer: s.data.buffer
          },
          [s.data.buffer]
        );
      },
      ping: (s) => this.reportPinglet(s),
      sendPinglets: () => this.sendPinglets(),
      getSettings: () => r,
      reset: () => t.reset(),
      delete: () => t.delete(),
      deleteLater: () => t.deleteLater(),
      isDeleted: () => t.isDeleted(),
      isAliasOf: (s) => t.isAliasOf(s),
      showDemoOverlay: () => u(this, A),
      showProductionOverlay: () => u(this, U)
    });
  }
  /**
   * This method is called when the worker is terminated.
   */
  [z]() {
  }
  /**
   * Terminates the workers and the Wasm runtime.
   */
  async terminate() {
    if (self.setTimeout(() => self.close, 5e3), !u(this, h)) {
      console.warn(
        "No Wasm module loaded during worker termination. Skipping cleanup."
      ), self.close();
      return;
    }
    u(this, h).terminateSdk(), await new Promise((o) => setTimeout(o, 0)), this.sendPinglets();
    const r = Date.now();
    for (; u(this, h).arePingRequestsInProgress() && Date.now() - r < 5e3; )
      await new Promise((o) => setTimeout(o, 100));
    y(this, h, void 0), console.debug("BlinkIdWorker terminated 🔴"), self.close();
  }
}
h = new WeakMap(), v = new WeakMap(), A = new WeakMap(), U = new WeakMap(), T = new WeakMap(), b = new WeakMap(), O = new WeakMap(), P = new WeakSet(), ye = async function({
  resourceUrl: t,
  variant: r,
  useLightweightBuild: o,
  initialMemory: s
}) {
  if (u(this, h)) {
    console.log("Wasm already loaded");
    return;
  }
  const n = r ?? await Ge(), m = o ? "lightweight" : "full", a = "BlinkIdModule", c = I(
    t,
    m,
    n
  ), i = I(c, `${a}.js`), l = I(c, `${a}.wasm`), d = I(c, `${a}.data`), f = await Ye(i), V = (await import(
    /* @vite-ignore */
    f
  )).default;
  s || (s = Ke() ? 700 : 200);
  const we = new WebAssembly.Memory({
    initial: re(s),
    maximum: re(2048),
    shared: n === "advanced-threads"
  });
  let S, E, q = 0;
  const be = 32, G = () => {
    if (!this.progressStatusCallback || !S || !E)
      return;
    const g = S.finished && E.finished, Y = S.loaded + E.loaded, K = S.contentLength + E.contentLength, ke = g ? 100 : Math.min(Math.round(Y / K * 100), 100), X = performance.now();
    X - q < be || (q = X, this.progressStatusCallback({
      loaded: Y,
      contentLength: K,
      progress: ke,
      finished: g
    }));
  }, Pe = (g) => {
    S = g, G();
  }, Se = (g) => {
    E = g, G();
  }, [Ee, xe] = await Promise.all([
    oe(
      l,
      "wasm",
      n,
      m,
      Pe
    ),
    oe(
      d,
      "data",
      n,
      m,
      Se
    )
  ]);
  if (this.progressStatusCallback && S && E) {
    const g = S.contentLength + E.contentLength;
    this.progressStatusCallback({
      loaded: g,
      contentLength: g,
      progress: 100,
      finished: !0
    });
  }
  if (y(this, h, await V({
    locateFile: (g) => `${c}/${n}/${g}`,
    // pthreads build breaks without this:
    // "Failed to execute 'createObjectURL' on 'URL': Overload resolution failed."
    mainScriptUrlOrBlob: f,
    wasmBinary: Ee,
    getPreloadedPackage() {
      return xe;
    },
    wasmMemory: we,
    noExitRuntime: !0
  })), !u(this, h))
    throw new Error("Failed to load Wasm module");
}, D = function(t) {
  const r = {
    data: {
      errorType: t.errorType,
      errorMessage: t.errorMessage
    },
    schemaName: "ping.error",
    schemaVersion: "1.0.0"
  };
  this.reportPinglet(r);
};
const ct = new it();
H(ct);
class lt {
  constructor(t) {
    x(this, "data");
    /** Needs to be 0 for sorting purposes */
    x(this, "sessionNumber", 0);
    x(this, "schemaName", "ping.sdk.init.start");
    x(this, "schemaVersion", "1.0.0");
    this.data = t;
  }
}
class ut extends Error {
  constructor(r, o) {
    super(r);
    x(this, "code");
    this.name = "LicenseError", this.code = o;
  }
}

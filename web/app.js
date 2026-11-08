/**
 * ChronosMatch — Operations Console
 * Single-file React application loaded natively via React.createElement.
 * Zero bundler, zero JSX compilation, zero external dependencies.
 */

const { useState, useEffect, createElement: h } = React;

function formatNumber(num) {
  if (num === null || num === undefined) return "—";
  return Number(num).toLocaleString();
}

function formatLatency(val) {
  if (val === null || val === undefined) return "Awaiting data";
  return `${Number(val).toFixed(2)} μs`;
}

function formatPrice(price) {
  if (price === null || price === undefined) return "—";
  return Number(price).toLocaleString();
}

function App() {
  const [data, setData] = useState(null);
  const [wsStatus, setWsStatus] = useState("CONNECTING");
  const [expandedWhaleId, setExpandedWhaleId] = useState(null);
  const [clock, setClock] = useState(new Date().toLocaleTimeString());

  // Clock tick
  useEffect(() => {
    const timer = setInterval(() => {
      setClock(new Date().toLocaleTimeString());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // WebSocket connection with REST fallback
  useEffect(() => {
    let ws = null;
    let fallbackInterval = null;
    let isMounted = true;

    function connect() {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.host;
      const wsUrl = `${protocol}//${host}/ws/live`;

      try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          if (!isMounted) return;
          setWsStatus("LIVE");
          if (fallbackInterval) {
            clearInterval(fallbackInterval);
            fallbackInterval = null;
          }
        };

        ws.onmessage = (event) => {
          if (!isMounted) return;
          try {
            const payload = JSON.parse(event.data);
            setData(payload);
          } catch (e) {
            console.error("Failed to parse websocket frame", e);
          }
        };

        ws.onclose = () => {
          if (!isMounted) return;
          setWsStatus("RECONNECTING");
          startFallback();
          setTimeout(connect, 2000);
        };

        ws.onerror = () => {
          if (ws) ws.close();
        };
      } catch (err) {
        startFallback();
        setTimeout(connect, 2000);
      }
    }

    function startFallback() {
      if (fallbackInterval) return;
      fallbackInterval = setInterval(async () => {
        try {
          const res = await fetch("/api/snapshot");
          if (res.ok && isMounted) {
            const payload = await res.json();
            setData(payload);
          }
        } catch (e) {
          // ignore network errors during reconnect
        }
      }, 1000);
    }

    connect();

    return () => {
      isMounted = false;
      if (ws) ws.close();
      if (fallbackInterval) clearInterval(fallbackInterval);
    };
  }, []);

  const overview = data?.engine_overview || {};
  const market = data?.market_snapshot || {};
  const whales = data?.whale_metrics || {};
  const activity = data?.recent_activity || [];
  const health = data?.engine_health || {};

  const isCython = health.cython_mode;

  return h("div", { className: "console-container" },
    // 1. Header
    h("header", { className: "console-header" },
      h("div", { className: "console-title-group" },
        h("div", { className: "console-title" }, "CHRONOSMATCH // OPERATIONS CONSOLE"),
        h("div", { className: "console-subtitle" }, "HFT MATCHING TELEMETRY")
      ),
      h("div", { className: "header-status-group" },
        // Connection status
        h("div", {
          className: `badge ${wsStatus === "LIVE" ? "badge-success" : "badge-warning"}`
        },
          h("span", { className: "badge-dot" }),
          wsStatus === "LIVE" ? "WS: LIVE" : `WS: ${wsStatus}`
        ),
        // Cython status badge
        h("div", {
          className: `badge ${isCython ? "badge-success" : "badge-warning"}`
        },
          h("span", { className: "badge-dot" }),
          isCython ? "CYTHON NATIVE" : "PYTHON FALLBACK"
        ),
        // Engine status
        h("div", {
          className: `badge ${overview.status === "RUNNING" ? "badge-success" : "badge-neutral"}`
        },
          h("span", { className: "badge-dot" }),
          overview.status || "IDLE"
        ),
        // Clock
        h("div", { className: "clock-display" }, clock)
      )
    ),

    // 2. Top Row: Engine Overview (A) + Market Snapshot (B)
    h("div", { className: "top-grid" },
      // Panel A: Engine Overview
      h("div", { className: "panel" },
        h("div", { className: "panel-header" },
          h("div", { className: "panel-title" }, "ENGINE OVERVIEW"),
          h("div", { className: "mono", style: { fontSize: "11px", color: "var(--text-muted)" } },
            `UPTIME: ${overview.uptime_seconds !== undefined ? `${overview.uptime_seconds}s` : "—"}`
          )
        ),
        h("div", { className: "panel-body" },
          h("div", { className: "metrics-cards-grid" },
            h("div", { className: "metric-card" },
              h("div", { className: "metric-label" }, "THROUGHPUT"),
              h("div", { className: "metric-value text-accent" },
                formatNumber(overview.orders_per_sec)
              ),
              h("div", { className: "metric-sub" }, "orders / sec")
            ),
            h("div", { className: "metric-card" },
              h("div", { className: "metric-label" }, "AVG LATENCY"),
              h("div", { className: "metric-value" },
                formatLatency(overview.latency_us)
              ),
              h("div", { className: "metric-sub" }, "processing time")
            ),
            h("div", { className: "metric-card" },
              h("div", { className: "metric-label" }, "TOTAL ORDERS"),
              h("div", { className: "metric-value" },
                formatNumber(overview.orders)
              ),
              h("div", { className: "metric-sub" }, "processed")
            ),
            h("div", { className: "metric-card" },
              h("div", { className: "metric-label" }, "TOTAL TRADES"),
              h("div", { className: "metric-value text-buy" },
                formatNumber(overview.trades)
              ),
              h("div", { className: "metric-sub" }, "executed")
            )
          )
        )
      ),

      // Panel B: Market Snapshot
      h("div", { className: "panel" },
        h("div", { className: "panel-header" },
          h("div", { className: "panel-title" }, "MARKET SNAPSHOT"),
          h("div", { className: "mono", style: { fontSize: "11px", color: "var(--text-muted)" } },
            `DEPTH: ${market.bids_levels || 0} BIDS / ${market.asks_levels || 0} ASKS`
          )
        ),
        h("div", { className: "panel-body" },
          h("div", { className: "market-cards-grid" },
            h("div", { className: "metric-card" },
              h("div", { className: "metric-label" }, "BEST BID"),
              h("div", { className: "metric-value text-buy" },
                formatPrice(market.best_bid)
              ),
              h("div", { className: "metric-sub" },
                market.bids_levels ? `${market.bids_levels} active level(s)` : "no resting bids"
              )
            ),
            h("div", { className: "metric-card" },
              h("div", { className: "metric-label" }, "BEST ASK"),
              h("div", { className: "metric-value text-sell" },
                formatPrice(market.best_ask)
              ),
              h("div", { className: "metric-sub" },
                market.asks_levels ? `${market.asks_levels} active level(s)` : "no resting asks"
              )
            ),
            h("div", { className: "metric-card" },
              h("div", { className: "metric-label" }, "SPREAD"),
              h("div", { className: "metric-value text-accent" },
                formatPrice(market.spread)
              ),
              h("div", { className: "metric-sub" }, "ask - bid")
            )
          )
        )
      )
    ),

    // 3. Section C: Whale Detection Log
    h("div", { className: "panel whale-panel" },
      h("div", { className: "panel-header" },
        h("div", { style: { display: "flex", alignItems: "center", gap: "10px" } },
          h("div", { className: "panel-title text-whale" }, "WHALE ORDER DETECTION LOG"),
          h("div", { style: { fontSize: "11px", color: "var(--text-muted)" } },
            "(AGGRESSIVE MULTI-LEVEL LIQUIDITY SWEEPS)"
          )
        ),
        h("div", { className: "badge badge-warning" },
          `${whales.total_whales || 0} DETECTED`
        )
      ),
      h("div", { className: "panel-body", style: { padding: "10px 14px" } },
        h("div", { className: "whale-list" },
          (!whales.recent_whales || whales.recent_whales.length === 0)
            ? h("div", { className: "whale-empty" },
                "No whale orders detected yet. Incoming orders sweeping ≥2 price levels will appear here."
              )
            : whales.recent_whales.map((w) => {
                const isExpanded = expandedWhaleId === w.order_id;
                return h("div", { key: `${w.order_id}-${w.timestamp_ns}`, className: "whale-item" },
                  h("div", {
                    className: "whale-summary",
                    onClick: () => setExpandedWhaleId(isExpanded ? null : w.order_id)
                  },
                    h("span", { className: "mono", style: { fontWeight: 700 } }, `ORDER #${w.order_id}`),
                    h("span", {
                      className: `badge ${w.side === "BUY" ? "badge-success" : "badge-danger"}`
                    }, w.side),
                    h("span", { className: "mono" }, `QTY: ${formatNumber(w.total_quantity)}`),
                    h("span", { className: "mono text-whale" }, `${w.levels_swept} LEVELS`),
                    h("span", { className: "whale-prices" },
                      `Prices: [${(w.execution_prices || []).join(", ")}]`
                    ),
                    h("span", {
                      className: `badge ${w.is_partial ? "badge-warning" : "badge-neutral"}`
                    }, w.is_partial ? "PARTIAL" : "FULL FILL"),
                    h("span", { className: "mono", style: { color: "var(--text-muted)", fontSize: "11px" } },
                      w.timestamp
                    ),
                    h("span", { className: "whale-expand-icon" }, isExpanded ? "▲" : "▼")
                  ),
                  // Expandable breakdown
                  isExpanded && h("div", { className: "whale-details" },
                    h("div", { className: "mono", style: { fontSize: "11px", color: "var(--text-muted)", marginBottom: "4px" } },
                      `Execution Breakdown (${w.trades.length} fill events across ${w.levels_swept} price levels):`
                    ),
                    h("table", { className: "whale-trades-table" },
                      h("thead", null,
                        h("tr", null,
                          h("th", null, "FILL #"),
                          h("th", null, "BUY ORDER"),
                          h("th", null, "SELL ORDER"),
                          h("th", null, "EXEC PRICE"),
                          h("th", null, "MATCHED QTY")
                        )
                      ),
                      h("tbody", null,
                        w.trades.map((t, idx) =>
                          h("tr", { key: idx },
                            h("td", null, `#${idx + 1}`),
                            h("td", null, `#${t.buy_order_id}`),
                            h("td", null, `#${t.sell_order_id}`),
                            h("td", { className: "text-accent" }, formatPrice(t.price)),
                            h("td", null, formatNumber(t.quantity))
                          )
                        )
                      )
                    )
                  )
                );
              })
        )
      )
    ),

    // 4. Bottom Row: Recent Activity Stream (D) + Engine Health (E)
    h("div", { className: "bottom-grid" },
      // Panel D: Recent Activity
      h("div", { className: "panel" },
        h("div", { className: "panel-header" },
          h("div", { className: "panel-title" }, "RECENT ACTIVITY STREAM"),
          h("div", { className: "mono", style: { fontSize: "11px", color: "var(--text-muted)" } },
            "LATEST EXECUTIONS & ALERTS (NEWEST FIRST)"
          )
        ),
        h("div", { className: "activity-table-wrapper" },
          activity.length === 0
            ? h("div", { className: "whale-empty" }, "Awaiting market orders...")
            : h("table", { className: "activity-table" },
                h("thead", null,
                  h("tr", null,
                    h("th", null, "TIME"),
                    h("th", null, "EVENT"),
                    h("th", null, "SIDE"),
                    h("th", null, "PRICE"),
                    h("th", null, "QTY"),
                    h("th", null, "DETAILS")
                  )
                ),
                h("tbody", null,
                  activity.slice(0, 30).map((act, i) => {
                    const isWhale = act.type === "WHALE_ALERT";
                    return h("tr", { key: i, className: isWhale ? "row-whale" : "" },
                      h("td", { style: { color: "var(--text-muted)" } }, act.time || "—"),
                      h("td", { style: { fontWeight: isWhale ? 700 : 500, color: isWhale ? "var(--color-whale)" : "var(--text-primary)" } },
                        act.symbol || "—"
                      ),
                      h("td", null,
                        h("span", {
                          className: `badge ${
                            act.side === "BUY" ? "badge-success" :
                            act.side === "SELL" ? "badge-danger" :
                            act.side === "WHALE" ? "badge-warning" : "badge-neutral"
                          }`
                        }, act.side || "MATCH")
                      ),
                      h("td", { className: isWhale ? "text-whale" : "text-accent" },
                        typeof act.price === "number" ? formatPrice(act.price) : act.price
                      ),
                      h("td", null, formatNumber(act.quantity)),
                      h("td", { style: { color: isWhale ? "var(--color-whale)" : "var(--text-muted)", fontSize: "11px" } },
                        act.details || (isWhale ? "Multi-level sweep" : "Execution fill")
                      )
                    );
                  })
                )
              )
        )
      ),

      // Panel E: Engine Health & Verification
      h("div", { className: "panel" },
        h("div", { className: "panel-header" },
          h("div", { className: "panel-title" }, "ENGINE HEALTH & TELEMETRY"),
          h("div", { className: "mono", style: { fontSize: "11px", color: "var(--text-muted)" } },
            "SUBSYSTEM INTEGRITY"
          )
        ),
        h("div", { className: "panel-body" },
          h("div", { className: "health-list" },
            // Matching Engine
            h("div", { className: "health-row" },
              h("div", null,
                h("div", { className: "health-label" }, "MATCHING ENGINE"),
                h("div", { className: "health-desc" }, "Price-time priority execution kernel")
              ),
              h("div", {
                className: `badge ${health.matching_engine === "RUNNING" ? "badge-success" : "badge-neutral"}`
              }, health.matching_engine || "IDLE")
            ),
            // OrderBook
            h("div", { className: "health-row" },
              h("div", null,
                h("div", { className: "health-label" }, "ORDER BOOK"),
                h("div", { className: "health-desc" },
                  `${market.bids_levels || 0} Bid / ${market.asks_levels || 0} Ask price levels`
                )
              ),
              h("div", { className: "badge badge-success" }, health.order_book || "READY")
            ),
            // Cython Execution Mode
            h("div", { className: "health-row" },
              h("div", null,
                h("div", { className: "health-label" }, "CYTHON COMPILED MODE"),
                h("div", { className: "health-desc" },
                  health.cython_available
                    ? "Extension binary: matching_engine_cy"
                    : "Extension binary not detected"
                )
              ),
              h("div", {
                className: `badge ${isCython ? "badge-success" : "badge-warning"}`
              },
                isCython ? "VERIFIED ACTIVE" : "PYTHON FALLBACK"
              )
            ),
            // Pipeline IPC
            h("div", { className: "health-row" },
              h("div", null,
                h("div", { className: "health-label" }, "SHARED RING BUFFER (IPC)"),
                h("div", { className: "health-desc" }, "Capacity: 1024 slots (33-byte >QQQBQ)")
              ),
              h("div", { className: "badge badge-success" }, "NOMINAL")
            )
          )
        )
      )
    )
  );
}

// Mount React Root
const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(h(App));


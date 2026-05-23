"use client";

import { useEffect, useMemo, useRef } from "react";
import cytoscape from "cytoscape";

const GRAPH_WIDTH = 860;
const GRAPH_HEIGHT = 460;

function formatNodeLabel(label, kind, focus) {
  const value = String(label || "").trim();
  if (!value) {
    return "Pending";
  }
  if (focus) {
    return value.length > 22 ? `${value.slice(0, 19)}...` : value;
  }

  const shortened = value
    .replace(/^ACC-/i, "")
    .replace(/^DEV-/i, "")
    .replace(/^MER-/i, "")
    .replace(/^GEO-/i, "");

  if (kind === "merchant") {
    return shortened.length > 16 ? `${shortened.slice(0, 13)}...` : shortened;
  }
  if (kind === "geo") {
    return shortened.length > 14 ? `${shortened.slice(0, 11)}...` : shortened;
  }
  return shortened.length > 15 ? `${shortened.slice(0, 12)}...` : shortened;
}

function nodeColor(kind, risk, focus) {
  if (focus) {
    return "#1a1a1a";
  }
  if (kind === "device") {
    return "#dce5f2";
  }
  if (kind === "merchant") {
    return "#e5eadf";
  }
  if (kind === "geo") {
    return "#ece4f2";
  }
  if (risk >= 82) {
    return "#f3d6dc";
  }
  if (risk >= 65) {
    return "#f7e2d0";
  }
  if (risk >= 40) {
    return "#f6edd4";
  }
  return "#e8efe4";
}

function edgeColor(kind) {
  if (kind === "device") {
    return "#b8c8dd";
  }
  if (kind === "merchant") {
    return "#b9c9b4";
  }
  if (kind === "geo") {
    return "#cfc3dc";
  }
  return "#d6cbbf";
}

function sanitizeElements(elements) {
  const seen = new Set();
  const nodes = [];
  const edges = [];

  for (const item of elements || []) {
    const data = item?.data;
    if (!data || typeof data.id !== "string" || !data.id.trim()) {
      continue;
    }
    if (seen.has(data.id)) {
      continue;
    }
    seen.add(data.id);

    if (typeof data.source === "string" && typeof data.target === "string") {
      edges.push({
        data: {
          id: data.id,
          source: data.source,
          target: data.target,
          kind: data.kind || "transfer",
          amount: Number(data.amount || 0)
        }
      });
      continue;
    }

    nodes.push({
      data: {
        id: data.id,
        label: data.label || data.id,
        displayLabel: formatNodeLabel(data.label || data.id, data.kind || "other", Boolean(data.focus)),
        kind: data.kind || "other",
        risk: Number(data.risk || 0),
        focus: Boolean(data.focus)
      }
    });
  }

  return { nodes, edges };
}

function assignPresetPositions(nodes) {
  const positions = new Map();
  const width = GRAPH_WIDTH;
  const height = GRAPH_HEIGHT;
  const focusNode = nodes.find((item) => item.data.focus) || nodes[0] || null;

  const byKind = {
    account: nodes.filter((item) => item.data.kind === "account" && item !== focusNode),
    device: nodes.filter((item) => item.data.kind === "device"),
    merchant: nodes.filter((item) => item.data.kind === "merchant"),
    geo: nodes.filter((item) => item.data.kind === "geo"),
    other: nodes.filter(
      (item) => !["account", "device", "merchant", "geo"].includes(item.data.kind) && item !== focusNode
    )
  };

  const placeColumn = (group, x, startY, gapY) => {
    group.forEach((item, index) => {
      positions.set(item.data.id, {
        x,
        y: startY + index * gapY
      });
    });
  };

  if (focusNode) {
    positions.set(focusNode.data.id, { x: width * 0.34, y: height * 0.5 });
  }

  placeColumn(byKind.device, width * 0.14, height * 0.24, 78);
  placeColumn(byKind.merchant, width * 0.18, height * 0.72, 70);
  placeColumn(byKind.geo, width * 0.68, height * 0.2, 72);
  placeColumn(byKind.account, width * 0.72, height * 0.32, 88);
  placeColumn(byKind.other, width * 0.52, height * 0.82, 68);

  return nodes.map((item, index) => ({
    ...item,
    position: positions.get(item.data.id) || {
      x: width * 0.5 + (index % 3) * 54,
      y: height * 0.5 + Math.floor(index / 3) * 54
    }
  }));
}

function graphSignature(nodes, edges) {
  return JSON.stringify({
    nodes: nodes.map((item) => ({
      id: item.data.id,
      label: item.data.label,
      kind: item.data.kind,
      risk: item.data.risk,
      focus: item.data.focus
    })),
    edges: edges.map((item) => ({
      id: item.data.id,
      source: item.data.source,
      target: item.data.target,
      kind: item.data.kind
    }))
  });
}

function fitViewport(cy) {
  if (!cy || cy.destroyed()) {
    return;
  }
  try {
    cy.resize();
    const elements = cy.elements();
    if (!elements.length) {
      return;
    }
    cy.fit(elements, 64);
    if (cy.zoom() > 0.96) {
      cy.zoom(0.96);
      cy.center(elements);
    }
  } catch {}
}

export default function TrustGraph({ elements, trustState, replayLabel }) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const presetPositionsRef = useRef(new Map());
  const { nodes, edges, signature, preparedElements } = useMemo(() => {
    const normalized = sanitizeElements(elements);
    const positionedNodes = assignPresetPositions(normalized.nodes);
    return {
      nodes: positionedNodes,
      edges: normalized.edges,
      signature: graphSignature(positionedNodes, normalized.edges),
      preparedElements: [...positionedNodes, ...normalized.edges]
    };
  }, [elements]);

  const nodeCounts = nodes.reduce(
    (acc, item) => {
      const kind = item?.data?.kind || "other";
      acc[kind] = (acc[kind] || 0) + 1;
      return acc;
    },
    { account: 0, device: 0, merchant: 0, geo: 0 }
  );
  const focusNode = nodes.find((item) => item?.data?.focus);
  const maxAccountRisk = nodes
    .filter((item) => item?.data?.kind === "account")
    .reduce((current, item) => Math.max(current, Number(item?.data?.risk || 0)), 0);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }

    let disposed = false;

    try {
      cyRef.current?.destroy();
    } catch {}
    cyRef.current = null;

    const cy = cytoscape({
      container: containerRef.current,
      elements: preparedElements,
      layout: { name: "preset", fit: false },
      boxSelectionEnabled: false,
      autoungrabify: false,
      autounselectify: false,
      userZoomingEnabled: true,
      userPanningEnabled: true,
      minZoom: 0.8,
      maxZoom: 1.8,
      style: [
        {
          selector: "node",
          style: {
            label: "data(displayLabel)",
            color: (ele) => (ele.data("focus") ? "#faf7f2" : "#1a1a1a"),
            "font-size": 10,
            "font-family": "IBM Plex Mono, monospace",
            "text-wrap": "wrap",
            "text-max-width": 76,
            "text-valign": "bottom",
            "text-margin-y": 8,
            width: 28,
            height: 28,
            "border-width": 1,
            "border-color": "#d7d0c4",
            "background-color": (ele) =>
              nodeColor(ele.data("kind"), Number(ele.data("risk") || 0), Boolean(ele.data("focus")))
          }
        },
        {
          selector: "node[kind = 'account']",
          style: {
            width: 30,
            height: 30,
            "font-size": 11
          }
        },
        {
          selector: "edge",
          style: {
            width: 1.15,
            opacity: 0.58,
            "line-color": (ele) => edgeColor(ele.data("kind")),
            "target-arrow-color": (ele) => edgeColor(ele.data("kind")),
            "target-arrow-shape": "triangle",
            "target-arrow-scale": 0.7,
            "curve-style": "bezier"
          }
        }
      ]
    });

    cyRef.current = cy;
    cy.nodes().grabify();
    presetPositionsRef.current = new Map(
      nodes.map((item) => [item.data.id, { x: item.position.x, y: item.position.y }])
    );

    requestAnimationFrame(() => {
      if (disposed || cyRef.current !== cy || cy.destroyed()) {
        return;
      }
      fitViewport(cy);
    });

    return () => {
      disposed = true;
      try {
        if (cyRef.current === cy) {
          cyRef.current = null;
        }
        cy.removeAllListeners();
        cy.destroy();
      } catch {}
    };
  }, [nodes, preparedElements, signature]);

  function handleFitView() {
    fitViewport(cyRef.current);
  }

  function handleResetLayout() {
    const cy = cyRef.current;
    if (!cy || cy.destroyed()) {
      return;
    }
    const presetPositions = presetPositionsRef.current;
    try {
      cy.nodes().positions((node) => presetPositions.get(node.id()) || node.position());
      fitViewport(cy);
    } catch {}
  }

  return (
    <div className="graph-shell">
      <div className="graph-toolbar">
        <div>
          <p className="eyebrow">Trust Memory Graph</p>
          <h3>{replayLabel || "Live relationship topology"}</h3>
          <div className="graph-toolbar-meta">
            <span>{focusNode?.data?.label || "Awaiting account"}</span>
            <span>
              {nodes.length} nodes | {edges.length} links
            </span>
            <span>{Math.round(maxAccountRisk)} max account risk</span>
          </div>
        </div>
        <div className="graph-toolbar-actions">
          <button type="button" className="graph-toolbar-button" onClick={handleFitView}>
            Fit view
          </button>
          <button type="button" className="graph-toolbar-button" onClick={handleResetLayout}>
            Reset layout
          </button>
          <div className={`state-pill state-${String(trustState || "Healthy").toLowerCase()}`}>
            {trustState || "Healthy"}
          </div>
        </div>
      </div>
      <div ref={containerRef} className="graph-canvas" />
      <div className="graph-footer">
        <div className="graph-legend">
          <span><i className="legend-dot legend-account" />Account {nodeCounts.account || 0}</span>
          <span><i className="legend-dot legend-device" />Device {nodeCounts.device || 0}</span>
          <span><i className="legend-dot legend-merchant" />Merchant {nodeCounts.merchant || 0}</span>
          <span><i className="legend-dot legend-geo" />Geo {nodeCounts.geo || 0}</span>
        </div>
        <p className="graph-interaction-note">Drag nodes, pan the canvas, and use fit view to recentre the case.</p>
      </div>
    </div>
  );
}

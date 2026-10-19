import { useEffect, useRef } from "react";
import cytoscape from "cytoscape";
import type { GraphData } from "../types";

interface Props {
  data: GraphData;
  onSelect: (documentId: number) => void;
}

export function RelationGraph({ data, onSelect }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const elements = [
      ...data.nodes.map((node) => ({
        data: {
          id: String(node.id),
          label: node.label.length > 14 ? `${node.label.slice(0, 14)}…` : node.label,
          ext: node.ext,
          center: node.center,
        },
      })),
      ...data.edges.map((edge, index) => ({
        data: {
          id: `e${index}`,
          source: String(edge.source),
          target: String(edge.target),
          label: edge.reason.length > 10 ? `${edge.reason.slice(0, 10)}…` : edge.reason,
        },
      })),
    ];
    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "font-size": 10,
            color: "var(--text)",
            "text-valign": "bottom",
            "text-margin-y": 4,
            width: 26,
            height: 26,
            "background-color": (element) => {
              if (element.data("center")) return "#0a84ff";
              switch (element.data("ext")) {
                case ".pdf":
                  return "#ff453a";
                case ".docx":
                  return "#0a84ff";
                case ".xlsx":
                  return "#30d158";
                case ".pptx":
                  return "#ff9f0a";
                case ".md":
                  return "#5e5ce6";
                default:
                  return "#8e8e93";
              }
            },
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.2,
            "line-color": "rgba(120,120,128,0.5)",
            "target-arrow-color": "rgba(120,120,128,0.5)",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            label: "data(label)",
            "font-size": 8,
            color: "var(--muted)",
            "text-rotation": "autorotate",
          },
        },
      ],
      layout: { name: "cose", animate: false, padding: 20 },
      wheelSensitivity: 0.2,
    });
    cy.on("tap", "node", (event) => {
      const id = Number(event.target.id());
      if (id) onSelect(id);
    });
    return () => cy.destroy();
  }, [data, onSelect]);

  if (!data.nodes.length) {
    return <div className="text-[12px] text-[var(--muted)]">暂无关系数据。</div>;
  }
  return <div ref={containerRef} className="h-[320px] w-full rounded-xl border border-[var(--border)]" />;
}

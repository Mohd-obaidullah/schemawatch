import React, { useState } from "react";
import { ChevronRight, ChevronDown, Braces, ListFilter } from "lucide-react";
import type { SchemaNode } from "@/types";

interface SchemaTreeProps {
  schema: Record<string, unknown> | SchemaNode;
  rootName?: string;
}

export function SchemaTree({ schema, rootName = "response" }: SchemaTreeProps): React.ReactElement {
  return (
    <div className="font-mono text-xs rounded-lg border bg-card/50 p-3 overflow-x-auto">
      <TreeNode
        name={rootName}
        node={schema as SchemaNode}
        isRequired={true}
        depth={0}
      />
    </div>
  );
}

function TreeNode({
  name,
  node,
  isRequired = false,
  depth = 0,
}: {
  name: string;
  node: SchemaNode | undefined;
  isRequired?: boolean;
  depth?: number;
}): React.ReactElement {
  const [isOpen, setIsOpen] = useState(true);

  if (!node) {
    return <div className="text-muted-foreground italic pl-4">unknown</div>;
  }

  const rawTypes = node.type;
  const types = Array.isArray(rawTypes) ? rawTypes : [rawTypes || "any"];
  const isObject = types.includes("object") && node.properties;
  const isArray = types.includes("array") && node.items;
  const hasChildren = Boolean(isObject || isArray);

  return (
    <div className="select-none py-0.5">
      <div
        className="flex items-center gap-1.5 hover:bg-muted/40 rounded px-1.5 py-0.5 -mx-1.5 cursor-pointer transition-colors"
        onClick={() => hasChildren && setIsOpen(!isOpen)}
        style={{ paddingLeft: `${depth * 1.25 + 0.375}rem` }}
      >
        {hasChildren ? (
          isOpen ? (
            <ChevronDown className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
          )
        ) : (
          <span className="w-3.5 shrink-0" />
        )}

        {isObject ? (
          <Braces className="w-3.5 h-3.5 text-sky-500 shrink-0" />
        ) : isArray ? (
          <ListFilter className="w-3.5 h-3.5 text-amber-500 shrink-0" />
        ) : null}

        <span className="font-semibold text-foreground">{name}</span>

        <span className="text-muted-foreground">:</span>

        <div className="flex items-center gap-1">
          {types.map((t, idx) => (
            <span
              key={idx}
              className={`px-1.5 py-0.2 rounded text-[10px] font-medium ${
                t === "object"
                  ? "bg-sky-100 text-sky-800 dark:bg-sky-950/60 dark:text-sky-300"
                  : t === "array"
                  ? "bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300"
                  : t === "string"
                  ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300"
                  : t === "integer" || t === "number"
                  ? "bg-purple-100 text-purple-800 dark:bg-purple-950/60 dark:text-purple-300"
                  : t === "boolean"
                  ? "bg-indigo-100 text-indigo-800 dark:bg-indigo-950/60 dark:text-indigo-300"
                  : "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300"
              }`}
            >
              {t}
            </span>
          ))}
        </div>

        {isRequired ? (
          <span className="text-[10px] text-red-500 font-bold ml-1" title="Required in baseline">
            *required
          </span>
        ) : (
          <span className="text-[10px] text-muted-foreground/60 ml-1">optional</span>
        )}
      </div>

      {hasChildren && isOpen && (
        <div className="border-l border-border/50 ml-3">
          {isObject &&
            node.properties &&
            Object.entries(node.properties).map(([propName, childNode]) => {
              const childRequired = node.required?.includes(propName) ?? false;
              const displayName = node.is_map && propName === "*" ? "* (dynamic map)" : propName;
              return (
                <TreeNode
                  key={propName}
                  name={displayName}
                  node={childNode}
                  isRequired={childRequired}
                  depth={depth + 1}
                />
              );
            })}

          {isArray && node.items && (
            <TreeNode
              name="[items]"
              node={node.items}
              isRequired={true}
              depth={depth + 1}
            />
          )}
        </div>
      )}
    </div>
  );
}

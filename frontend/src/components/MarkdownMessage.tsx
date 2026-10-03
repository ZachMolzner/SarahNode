import React, { Fragment } from "react";

type MarkdownMessageProps = {
  content: string;
};

type Block =
  | { type: "paragraph"; text: string }
  | { type: "heading"; level: number; text: string }
  | { type: "unordered"; items: string[] }
  | { type: "ordered"; items: string[] }
  | { type: "code"; language: string; text: string };

function parseBlocks(content: string): Block[] {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let paragraph: string[] = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    const text = paragraph.join(" ").trim();
    if (text) blocks.push({ type: "paragraph", text });
    paragraph = [];
  };

  let index = 0;
  while (index < lines.length) {
    const line = lines[index];

    if (line.trim().startsWith("```")) {
      flushParagraph();
      const language = line.trim().slice(3).trim();
      index += 1;
      const code: string[] = [];
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        code.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      blocks.push({ type: "code", language, text: code.join("\n") });
      continue;
    }

    const heading = /^(#{1,3})\s+(.+)$/.exec(line.trim());
    if (heading) {
      flushParagraph();
      blocks.push({
        type: "heading",
        level: heading[1].length,
        text: heading[2].trim(),
      });
      index += 1;
      continue;
    }

    const unordered = /^\s*[-*]\s+(.+)$/.exec(line);
    if (unordered) {
      flushParagraph();
      const items: string[] = [];
      while (index < lines.length) {
        const match = /^\s*[-*]\s+(.+)$/.exec(lines[index]);
        if (!match) break;
        items.push(match[1].trim());
        index += 1;
      }
      blocks.push({ type: "unordered", items });
      continue;
    }

    const ordered = /^\s*\d+[.)]\s+(.+)$/.exec(line);
    if (ordered) {
      flushParagraph();
      const items: string[] = [];
      while (index < lines.length) {
        const match = /^\s*\d+[.)]\s+(.+)$/.exec(lines[index]);
        if (!match) break;
        items.push(match[1].trim());
        index += 1;
      }
      blocks.push({ type: "ordered", items });
      continue;
    }

    if (!line.trim()) {
      flushParagraph();
      index += 1;
      continue;
    }

    paragraph.push(line.trim());
    index += 1;
  }

  flushParagraph();
  return blocks;
}

function renderInline(text: string) {
  const tokenPattern = /(`[^`]+`|\*\*[^*]+\*\*)/g;
  const parts = text.split(tokenPattern).filter(Boolean);

  return parts.map((part, index) => {
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code key={index} style={styles.inlineCode}>
          {part.slice(1, -1)}
        </code>
      );
    }

    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }

    return <Fragment key={index}>{part}</Fragment>;
  });
}

export function MarkdownMessage({ content }: MarkdownMessageProps) {
  const blocks = parseBlocks(content);

  return (
    <div style={styles.root}>
      {blocks.map((block, index) => {
        if (block.type === "heading") {
          const headingStyle =
            block.level === 1
              ? styles.heading1
              : block.level === 2
                ? styles.heading2
                : styles.heading3;
          return (
            <div key={index} style={headingStyle}>
              {renderInline(block.text)}
            </div>
          );
        }

        if (block.type === "unordered") {
          return (
            <ul key={index} style={styles.list}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex} style={styles.listItem}>
                  {renderInline(item)}
                </li>
              ))}
            </ul>
          );
        }

        if (block.type === "ordered") {
          return (
            <ol key={index} style={styles.list}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex} style={styles.listItem}>
                  {renderInline(item)}
                </li>
              ))}
            </ol>
          );
        }

        if (block.type === "code") {
          return (
            <div key={index} style={styles.codeShell}>
              {block.language && (
                <div style={styles.codeLanguage}>{block.language}</div>
              )}
              <pre style={styles.codeBlock}>
                <code>{block.text}</code>
              </pre>
            </div>
          );
        }

        return (
          <p key={index} style={styles.paragraph}>
            {renderInline(block.text)}
          </p>
        );
      })}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  root: {
    display: "flex",
    flexDirection: "column",
    gap: "10px",
    overflowWrap: "anywhere",
  },
  paragraph: {
    margin: 0,
    lineHeight: 1.58,
  },
  heading1: {
    marginTop: "4px",
    fontSize: "19px",
    lineHeight: 1.3,
    fontWeight: 750,
  },
  heading2: {
    marginTop: "4px",
    fontSize: "17px",
    lineHeight: 1.35,
    fontWeight: 730,
  },
  heading3: {
    marginTop: "2px",
    fontSize: "15px",
    lineHeight: 1.4,
    fontWeight: 700,
  },
  list: {
    margin: 0,
    paddingLeft: "22px",
    display: "flex",
    flexDirection: "column",
    gap: "6px",
  },
  listItem: {
    lineHeight: 1.55,
    paddingLeft: "2px",
  },
  inlineCode: {
    fontFamily:
      "'Cascadia Code', 'SFMono-Regular', Consolas, 'Liberation Mono', monospace",
    fontSize: "0.92em",
    background: "#0c1119",
    border: "1px solid #303949",
    borderRadius: "5px",
    padding: "1px 5px",
    color: "#d9e7ff",
  },
  codeShell: {
    overflow: "hidden",
    borderRadius: "10px",
    border: "1px solid #303949",
    background: "#090d13",
  },
  codeLanguage: {
    padding: "7px 11px",
    borderBottom: "1px solid #252d39",
    color: "#8491a5",
    fontSize: "11px",
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
  },
  codeBlock: {
    margin: 0,
    padding: "13px 14px",
    overflowX: "auto",
    whiteSpace: "pre",
    fontFamily:
      "'Cascadia Code', 'SFMono-Regular', Consolas, 'Liberation Mono', monospace",
    fontSize: "13px",
    lineHeight: 1.55,
    color: "#e6edf7",
  },
};

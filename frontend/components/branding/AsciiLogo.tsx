/**
 * Onchor.ai — ASCII logo identical to `backend/ui.py` (ASCII_LOGO).
 * Displayed in monospace + brand color. Preserves spaces.
 */
export const ASCII_LOGO = String.raw`   ____             __                     ___    ____
  / __ \____  _____/ /_  ____  _____      /   |  /  _/
 / / / / __ \/ ___/ __ \/ __ \/ ___/_____/ /| |  / /  
/ /_/ / / / / /__/ / / / /_/ / /  /_____/ ___ |_/ /   
\____/_/ /_/\___/_/ /_/\____/_/        /_/  |_/___/   `;

type Props = {
  className?: string;
  glow?: boolean;
};

export function AsciiLogo({ className = "", glow = true }: Props) {
  return (
    <pre
      aria-label="Onchor-AI"
      className={[
        "font-mono leading-tight whitespace-pre text-[--terminal-brand]",
        glow ? "glow-brand" : "",
        className,
      ].join(" ")}
    >
      {ASCII_LOGO}
    </pre>
  );
}

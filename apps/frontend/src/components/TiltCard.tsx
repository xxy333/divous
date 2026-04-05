import { useRef, useState, CSSProperties, ReactNode } from "react";
import styles from "./TiltCard.module.css";

interface Props {
  children: ReactNode;
  className?: string;
  href?: string;
}

export default function TiltCard({ children, className = "", href }: Props) {
  const ref = useRef<HTMLElement>(null);
  const [tilt, setTilt] = useState<CSSProperties>({});
  const [glow, setGlow] = useState<CSSProperties>({ opacity: 0 });

  const onMove = (e: React.MouseEvent<HTMLElement>) => {
    const el = ref.current;
    if (!el) return;
    const { left, top, width, height } = el.getBoundingClientRect();
    const x = e.clientX - left;
    const y = e.clientY - top;
    const rx = ((y / height) - 0.5) * -18;
    const ry = ((x / width)  - 0.5) *  18;
    setTilt({
      transform: `perspective(700px) rotateX(${rx}deg) rotateY(${ry}deg) scale3d(1.04,1.04,1.04)`,
      transition: "transform 0.08s linear",
    });
    setGlow({
      opacity: 1,
      background: `radial-gradient(circle 140px at ${x}px ${y}px, rgba(123,156,255,0.14), transparent 70%)`,
      transition: "opacity 0.15s ease",
    });
  };

  const onLeave = () => {
    setTilt({
      transform: "perspective(700px) rotateX(0deg) rotateY(0deg) scale3d(1,1,1)",
      transition: "transform 0.45s cubic-bezier(.22,.68,0,1.2)",
    });
    setGlow({ opacity: 0, transition: "opacity 0.3s ease" });
  };

  const inner = (
    <>
      <div className={styles.glowOverlay} style={glow} />
      {children}
    </>
  );

  if (href) {
    return (
      <a
        ref={ref as React.RefObject<HTMLAnchorElement>}
        href={href}
        className={className}
        style={{ ...tilt, position: "relative", overflow: "hidden" }}
        onMouseMove={onMove}
        onMouseLeave={onLeave}
      >
        {inner}
      </a>
    );
  }

  return (
    <div
      ref={ref as React.RefObject<HTMLDivElement>}
      className={className}
      style={{ ...tilt, position: "relative", overflow: "hidden" }}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
    >
      {inner}
    </div>
  );
}
